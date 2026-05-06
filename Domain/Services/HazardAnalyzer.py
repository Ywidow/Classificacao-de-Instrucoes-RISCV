from dataclasses import dataclass, field
from typing import Optional

from Domain.Entities.InstructionDetails import InstructionDetails
from Domain.Enums.InstructionType import InstructionType
from Domain.Enums.OpCode import OpCode

NOP_HEX = '00000013'  # addi x0, x0, 0 — instrução que não faz nada

# Tipos de instrução que carregam da memória (lw, lh, lb, lhu, lbu)
LOAD_TYPES = frozenset({
    InstructionType.ILB, InstructionType.ILH, InstructionType.ILW,
    InstructionType.ILBU, InstructionType.ILHU,
})

# Tipos de instrução de desvio condicional (beq, bne, blt, bge, bltu, bgeu)
BRANCH_TYPES = frozenset({
    InstructionType.BBEQ, InstructionType.BBNE, InstructionType.BBLT,
    InstructionType.BBGE, InstructionType.BBLTU, InstructionType.BBGEU,
})

# Opcodes cujas instruções escrevem em rd
WRITES_RD_OPCODES = frozenset({
    OpCode.U0110111, OpCode.U0010111, OpCode.J1101111, OpCode.I1100111,
    OpCode.I0000011, OpCode.I0010011, OpCode.R0110011,
})

# Opcodes cujas instruções leem rs1
READS_RS1_OPCODES = frozenset({
    OpCode.I1100111, OpCode.B1100011, OpCode.I0000011, OpCode.S0100011,
    OpCode.I0010011, OpCode.R0110011,
})

# Opcodes cujas instruções leem rs2
READS_RS2_OPCODES = frozenset({
    OpCode.B1100011, OpCode.S0100011, OpCode.R0110011,
})


# Representa uma linha na sequência do pipeline — pode ser uma instrução real ou um NOP inserido
@dataclass
class InstructionRow:
    inst: InstructionDetails
    is_nop: bool
    original_idx: Optional[int]  # índice original da instrução (None se for NOP inserido)
    note: str = ""               # observação sobre hazard ou recálculo de offset


# Representa um hazard detectado — guarda o índice da instrução e uma descrição legível
@dataclass
class HazardReport:
    instr_idx: int
    description: str


def make_nop() -> InstructionDetails:
    # Cria uma instrução NOP (addi x0, x0, 0) para ser inserida no pipeline
    return InstructionDetails(NOP_HEX)


def _get_rd(inst: InstructionDetails) -> Optional[int]:
    # Retorna o registrador destino (rd) da instrução, ou None se ela não escreve em nenhum.
    # Escrita em x0 é ignorada porque x0 é sempre zero e nunca causa hazard.
    if inst.opCode not in WRITES_RD_OPCODES:
        return None
    rd = int(inst.binInstruction[20:25], 2)
    return rd if rd != 0 else None


def _get_rs1(inst: InstructionDetails) -> Optional[int]:
    # Retorna o registrador fonte rs1, ou None se a instrução não lê rs1.
    if inst.opCode in READS_RS1_OPCODES:
        return int(inst.binInstruction[12:17], 2)
    return None


def _get_rs2(inst: InstructionDetails) -> Optional[int]:
    # Retorna o registrador fonte rs2, ou None se a instrução não lê rs2.
    if inst.opCode in READS_RS2_OPCODES:
        return int(inst.binInstruction[7:12], 2)
    return None


def _get_branch_offset(inst: InstructionDetails) -> int:
    # Extrai o offset de desvio em bytes de instruções B-type (beq, bne...) e J-type (jal).
    # O resultado é um valor signed — negativo significa desvio para trás.
    b = inst.binInstruction
    if inst.type in BRANCH_TYPES:
        # Formato B-type: os bits do imediato ficam espalhados na instrução.
        # Monta: imm[12] | imm[11] | imm[10:5] | imm[4:1] | 0
        bits = b[0] + b[24] + b[1:7] + b[20:24] + '0'
        val = int(bits, 2)
        if b[0] == '1':  # bit de sinal — se 1, o offset é negativo
            val -= (1 << 13)
        return val
    if inst.type == InstructionType.JJAL:
        # Formato J-type: imm[20] | imm[19:12] | imm[11] | imm[10:1] | 0
        bits = b[0] + b[12:20] + b[11] + b[1:11] + '0'
        val = int(bits, 2)
        if b[0] == '1':
            val -= (1 << 21)
        return val
    return 0


def _encode_with_new_offset(inst: InstructionDetails, new_offset: int) -> InstructionDetails:
    # Reconstrói a instrução de desvio/salto com um novo offset.
    # Necessário porque ao inserir NOPs o endereço alvo muda.
    b = inst.binInstruction
    if inst.type in BRANCH_TYPES:
        n = new_offset & 0x1FFF
        imm = format(n, '013b')
        # Remonta os bits do imediato nos campos corretos do formato B-type
        new_bin = (imm[0] + imm[2:8] + b[7:12] + b[12:17] + b[17:20]
                   + imm[8:12] + imm[1] + b[25:])
        return InstructionDetails(format(int(new_bin, 2), '08x'))
    if inst.type == InstructionType.JJAL:
        n = new_offset & 0x1FFFFF
        imm = format(n, '021b')
        # Remonta os bits do imediato nos campos corretos do formato J-type
        new_bin = (imm[0] + imm[10:20] + imm[9] + imm[1:9] + b[20:25] + b[25:])
        return InstructionDetails(format(int(new_bin, 2), '08x'))
    return inst


def _run(
    instructions: list[InstructionDetails],
    compute_data_nops,
    control_nops: int,
    base_addr: int,
) -> list[InstructionRow]:
    # Função central do analisador. Faz uma única passagem nas instruções e:
    #   1. Insere NOPs de dados onde necessário (usando compute_data_nops)
    #   2. Insere NOPs de controle após cada desvio/salto (se control_nops > 0)
    #   3. Recalcula os offsets de todos os desvios e saltos

    # reg_avail[r]: posição mínima na nova sequência em que r pode ser lido sem stall (sem forwarding)
    reg_avail = [0] * 32
    # reg_load_avail[r]: igual, mas só atualizado para loads (usado no modo com forwarding)
    reg_load_avail = [0] * 32

    # Mapeia índice original → índice na nova sequência (com NOPs), para recalcular offsets depois
    original_to_new: dict[int, int] = {}
    # Lista bruta: (instrução, é_nop, índice_original)
    raw: list[tuple[InstructionDetails, bool, Optional[int]]] = []

    for orig_idx, inst in enumerate(instructions):
        # Verifica quantos NOPs de dados precisam ser inseridos antes desta instrução
        nops = compute_data_nops(reg_avail, reg_load_avail, inst, len(raw))
        for _ in range(nops):
            raw.append((make_nop(), True, None))

        # Registra em qual posição da nova sequência esta instrução ficou
        original_to_new[orig_idx] = len(raw)
        raw.append((inst, False, orig_idx))

        # Atualiza a disponibilidade do registrador destino após esta instrução
        rd = _get_rd(inst)
        if rd is not None:
            # Sem forwarding: rd fica disponível 4 posições depois (WB completa no ciclo p+4)
            reg_avail[rd] = len(raw) + 3
            if inst.type in LOAD_TYPES:
                # Com forwarding: load-use exige 1 NOP — dado sai do MEM no ciclo p+3,
                # mas o leitor precisa no EX do ciclo p+2 se vier logo após
                reg_load_avail[rd] = len(raw) + 1
            else:
                reg_load_avail[rd] = 0

        # Se é desvio/salto e a técnica usa NOPs de controle, insere após a instrução
        if control_nops and (inst.type in BRANCH_TYPES or inst.type == InstructionType.JJAL):
            for _ in range(control_nops):
                raw.append((make_nop(), True, None))

    # Segunda passagem: recalcula os offsets dos desvios/saltos deslocados pelos NOPs inseridos
    rows: list[InstructionRow] = []
    for new_idx, (inst, is_nop, orig_idx) in enumerate(raw):
        if is_nop:
            rows.append(InstructionRow(inst, True, None))
            continue

        note = ""
        updated = inst

        if inst.type in BRANCH_TYPES or inst.type == InstructionType.JJAL:
            old_off = _get_branch_offset(inst)
            orig_target_byte = orig_idx * 4 + old_off
            orig_target_idx = orig_target_byte // 4

            if orig_target_byte % 4 == 0 and 0 <= orig_target_idx < len(instructions):
                # Alvo é uma instrução interna — usa o mapeamento para achar a nova posição
                new_target_idx = original_to_new[orig_target_idx]
                new_off = (new_target_idx - new_idx) * 4
            else:
                # Alvo externo ao bloco — mantém o endereço absoluto
                orig_target_addr = base_addr + orig_idx * 4 + old_off
                new_branch_addr = base_addr + new_idx * 4
                new_off = orig_target_addr - new_branch_addr

            if new_off != old_off:
                note = f"Endereco desvio: {old_off:+d} -> {new_off:+d} bytes"
                updated = _encode_with_new_offset(inst, new_off)
            else:
                note = f"Endereco desvio: {old_off:+d} bytes (sem mudanca)"

        rows.append(InstructionRow(updated, False, orig_idx, note))

    return rows


# ── Sequência demo ─────────────────────────────────────────────────────────────
# Funções auxiliares para codificar instruções RISC-V manualmente (usadas na demo)

def _encode_r(rd: int, rs1: int, rs2: int, funct3: int = 0, funct7: int = 0) -> str:
    # Monta o hex de uma instrução tipo R (add, sub, and, or...)
    v = (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0110011
    return format(v, '08x')


def _encode_lw(rd: int, rs1: int, imm: int = 0) -> str:
    # Monta o hex de uma instrução lw
    v = ((imm & 0xFFF) << 20) | (rs1 << 15) | (0b010 << 12) | (rd << 7) | 0b0000011
    return format(v, '08x')


def _encode_beq(rs1: int, rs2: int, offset: int) -> str:
    # Monta o hex de uma instrução beq com o offset dado
    b12   = (offset >> 12) & 1
    b11   = (offset >> 11) & 1
    b10_5 = (offset >> 5) & 0x3F
    b4_1  = (offset >> 1) & 0xF
    v = ((b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15)
         | (b4_1 << 8) | (b11 << 7) | 0b1100011)
    return format(v, '08x')


def create_demo_sequence() -> list[InstructionDetails]:
    # Cria uma sequência de instruções artificial com todos os tipos de hazard,
    # usada nas abas de demonstração da interface gráfica.
    #
    # 0: add  x1, x2, x3   → escreve x1
    # 1: add  x4, x1, x5   → RAW em x1 (escrito na 0)
    # 2: add  x6, x4, x7   → RAW em x4 (escrito na 1)
    # 3: lw   x8, 0(x6)    → RAW em x6 (escrito na 2) + é um load
    # 4: add  x9, x8, x1   → load-use em x8 (carregado na 3)
    # 5: beq  x1, x4, +8   → conflito de controle, salta para instrução 7
    # 6: add  x10, x2, x3  → pode ser descartada se o desvio for tomado
    # 7: add  x11, x1, x4  → alvo do desvio
    hexes = [
        _encode_r(1, 2, 3),
        _encode_r(4, 1, 5),
        _encode_r(6, 4, 7),
        _encode_lw(8, 6, 0),
        _encode_r(9, 8, 1),
        _encode_beq(1, 4, 8),
        _encode_r(10, 2, 3),
        _encode_r(11, 1, 4),
    ]
    return [InstructionDetails(h) for h in hexes]


# ── Funções públicas de inserção de NOPs ──────────────────────────────────────

def insert_nops_no_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Resolve conflitos de dados SEM forwarding.
    # Para cada instrução, verifica se rs1 ou rs2 ainda não foram escritos
    # (reg_avail indica a posição mínima em que cada registrador pode ser lido).
    # Insere até 3 NOPs por conflito RAW.
    def compute(reg_avail, _load, inst, pos):
        rs1, rs2 = _get_rs1(inst), _get_rs2(inst)
        n = 0
        if rs1 and rs1 != 0:
            n = max(n, reg_avail[rs1] - pos)
        if rs2 and rs2 != 0:
            n = max(n, reg_avail[rs2] - pos)
        return max(0, n)

    return _run(instructions, compute, 0, base_addr)


def insert_nops_with_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Resolve conflitos de dados COM forwarding (EX→EX e MEM→EX).
    # Com forwarding a maioria dos RAW some — só o load-use ainda precisa de 1 NOP,
    # porque o dado do lw só sai da memória no MEM, depois que o leitor já passou pelo EX.
    def compute(_avail, reg_load_avail, inst, pos):
        rs1, rs2 = _get_rs1(inst), _get_rs2(inst)
        n = 0
        if rs1 and rs1 != 0:
            n = max(n, reg_load_avail[rs1] - pos)
        if rs2 and rs2 != 0:
            n = max(n, reg_load_avail[rs2] - pos)
        return max(0, n)

    return _run(instructions, compute, 0, base_addr)


def insert_nops_control_hazard(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Resolve conflitos de controle inserindo 2 NOPs após cada desvio ou salto.
    # O desvio é resolvido no EX (ciclo 3), então 2 instruções já entraram no pipeline
    # e precisam ser descartadas. Forwarding de dados não ajuda aqui.
    return _run(instructions, lambda *_: 0, 2, base_addr)


def insert_nops_integrated_no_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Solução integrada SEM forwarding: trata dados e controle juntos em uma passagem.
    # Dados: até 3 NOPs por RAW. Controle: 2 NOPs após cada desvio/salto.
    def compute(reg_avail, _load, inst, pos):
        rs1, rs2 = _get_rs1(inst), _get_rs2(inst)
        n = 0
        if rs1 and rs1 != 0:
            n = max(n, reg_avail[rs1] - pos)
        if rs2 and rs2 != 0:
            n = max(n, reg_avail[rs2] - pos)
        return max(0, n)

    return _run(instructions, compute, 2, base_addr)


def insert_nops_integrated_with_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Solução integrada COM forwarding: trata dados e controle juntos em uma passagem.
    # Dados: apenas load-use precisa de 1 NOP. Controle: 2 NOPs após cada desvio/salto.
    def compute(_avail, reg_load_avail, inst, pos):
        rs1, rs2 = _get_rs1(inst), _get_rs2(inst)
        n = 0
        if rs1 and rs1 != 0:
            n = max(n, reg_load_avail[rs1] - pos)
        if rs2 and rs2 != 0:
            n = max(n, reg_load_avail[rs2] - pos)
        return max(0, n)

    return _run(instructions, compute, 2, base_addr)


# ── Detecção de hazards (sem inserção de NOPs) ────────────────────────────────

def detect_data_hazards_no_forwarding(instructions: list[InstructionDetails]) -> list[HazardReport]:
    # Detecta conflitos RAW no código original, assumindo que não há forwarding.
    # Verifica as 3 instruções anteriores de cada instrução: se alguma delas escreve
    # em um registrador que esta instrução lê, há um hazard.
    # dist=1 → 3 NOPs necessários, dist=2 → 2 NOPs, dist=3 → 1 NOP.
    reports = []
    for i in range(len(instructions)):
        inst = instructions[i]
        rs1 = _get_rs1(inst)
        rs2 = _get_rs2(inst)
        if rs1 is None and rs2 is None:
            continue
        hazards = []
        for dist in range(1, 4):
            j = i - dist
            if j < 0:
                break
            rd = _get_rd(instructions[j])
            if rd is None:
                continue
            regs = []
            if rs1 == rd:
                regs.append("rs1")
            if rs2 == rd:
                regs.append("rs2")
            if regs:
                nops = 4 - dist
                hazards.append(f"x{rd} ({', '.join(regs)}, dist={dist}, NOPs={nops})")
        if hazards:
            reports.append(HazardReport(i, f"[Instr {i}] RAW hazard: {'; '.join(hazards)}"))
    return reports


def detect_data_hazards_with_forwarding(instructions: list[InstructionDetails]) -> list[HazardReport]:
    # Detecta conflitos load-use no código original, assumindo forwarding completo.
    # Com forwarding, o único caso que ainda precisa de NOP é quando um lw é seguido
    # imediatamente por uma instrução que lê o registrador que ele carregou.
    reports = []
    for i in range(1, len(instructions)):
        inst = instructions[i]
        rs1 = _get_rs1(inst)
        rs2 = _get_rs2(inst)
        prev = instructions[i - 1]
        if prev.type not in LOAD_TYPES:
            continue
        rd = _get_rd(prev)
        if rd is None:
            continue
        regs = []
        if rs1 == rd:
            regs.append("rs1")
        if rs2 == rd:
            regs.append("rs2")
        if regs:
            reports.append(HazardReport(
                i,
                f"[Instr {i}] Load-use hazard: x{rd} ({', '.join(regs)}), 1 NOP necessario"
            ))
    return reports


def detect_control_hazards(instructions: list[InstructionDetails]) -> list[HazardReport]:
    # Detecta todos os conflitos de controle: desvios condicionais (beq, bne...)
    # e saltos incondicionais (jal). Cada um desses causa um stall de 2 ciclos.
    reports = []
    for i, inst in enumerate(instructions):
        if inst.type in BRANCH_TYPES:
            off = _get_branch_offset(inst)
            reports.append(HazardReport(
                i,
                f"[Instr {i}] Desvio condicional ({inst.type.instr_type}): offset={off:+d} bytes, 2 NOPs"
            ))
        elif inst.type == InstructionType.JJAL:
            off = _get_branch_offset(inst)
            reports.append(HazardReport(
                i,
                f"[Instr {i}] Salto incondicional (JAL): offset={off:+d} bytes, 2 NOPs"
            ))
    return reports


# ── Geração de arquivo de saída ───────────────────────────────────────────────

def write_rows_to_file(rows: list[InstructionRow], filename: str) -> None:
    # Grava a sequência de instruções (já com NOPs inseridos) em um arquivo de texto,
    # uma instrução por linha no formato hexadecimal.
    with open(filename, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(row.inst.hexInstruction.lower() + '\n')

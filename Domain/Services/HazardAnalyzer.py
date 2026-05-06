from dataclasses import dataclass, field
from typing import Optional

from Domain.Entities.InstructionDetails import InstructionDetails
from Domain.Enums.InstructionType import InstructionType
from Domain.Enums.OpCode import OpCode

NOP_HEX = '00000013'  # addi x0, x0, 0 — não faz nada, é o NOP padrão do RISC-V

# Instruções que lêem da memória — são as que causam load-use hazard
LOAD_TYPES = frozenset({
    InstructionType.ILB, InstructionType.ILH, InstructionType.ILW,
    InstructionType.ILBU, InstructionType.ILHU,
})

# Desvios condicionais — todos causam conflito de controle
BRANCH_TYPES = frozenset({
    InstructionType.BBEQ, InstructionType.BBNE, InstructionType.BBLT,
    InstructionType.BBGE, InstructionType.BBLTU, InstructionType.BBGEU,
})

# Opcodes de instruções que escrevem em rd (podem causar RAW hazard)
WRITES_RD_OPCODES = frozenset({
    OpCode.U0110111, OpCode.U0010111, OpCode.J1101111, OpCode.I1100111,
    OpCode.I0000011, OpCode.I0010011, OpCode.R0110011,
})

# Opcodes de instruções que leem rs1
READS_RS1_OPCODES = frozenset({
    OpCode.I1100111, OpCode.B1100011, OpCode.I0000011, OpCode.S0100011,
    OpCode.I0010011, OpCode.R0110011,
})

# Opcodes de instruções que leem rs2
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
    # Cria um NOP para inserir entre as instruções
    return InstructionDetails(NOP_HEX)


def _get_rd(inst: InstructionDetails) -> Optional[int]:
    # Retorna o rd da instrução, ou None se ela não escreve em nenhum registrador.
    # x0 é ignorado — ele é sempre zero e nunca vai causar hazard.
    if inst.opCode not in WRITES_RD_OPCODES:
        return None
    rd = int(inst.binInstruction[20:25], 2)
    return rd if rd != 0 else None


def _get_rs1(inst: InstructionDetails) -> Optional[int]:
    # Retorna rs1 se a instrução lê esse registrador, senão None
    if inst.opCode in READS_RS1_OPCODES:
        return int(inst.binInstruction[12:17], 2)
    return None


def _get_rs2(inst: InstructionDetails) -> Optional[int]:
    # Retorna rs2 se a instrução lê esse registrador, senão None
    if inst.opCode in READS_RS2_OPCODES:
        return int(inst.binInstruction[7:12], 2)
    return None


def _get_branch_offset(inst: InstructionDetails) -> int:
    # Extrai o offset de desvio em bytes. Negativo = salta para trás.
    # Os bits do imediato ficam espalhados na instrução, então precisa remontar na ordem certa.
    b = inst.binInstruction
    if inst.type in BRANCH_TYPES:
        # B-type: imm[12|11|10:5|4:1|0]
        bits = b[0] + b[24] + b[1:7] + b[20:24] + '0'
        val = int(bits, 2)
        if b[0] == '1':  # bit de sinal
            val -= (1 << 13)
        return val
    if inst.type == InstructionType.JJAL:
        # J-type: imm[20|19:12|11|10:1|0]
        bits = b[0] + b[12:20] + b[11] + b[1:11] + '0'
        val = int(bits, 2)
        if b[0] == '1':
            val -= (1 << 21)
        return val
    return 0


def _encode_with_new_offset(inst: InstructionDetails, new_offset: int) -> InstructionDetails:
    # Reconstrói a instrução com o novo offset já corrigido.
    # Precisa desmontar e remontar os bits do imediato porque o formato RISC-V
    # espalha os bits do offset em posições não contíguas na instrução.
    b = inst.binInstruction
    if inst.type in BRANCH_TYPES:
        n = new_offset & 0x1FFF
        imm = format(n, '013b')
        new_bin = (imm[0] + imm[2:8] + b[7:12] + b[12:17] + b[17:20]
                   + imm[8:12] + imm[1] + b[25:])
        return InstructionDetails(format(int(new_bin, 2), '08x'))
    if inst.type == InstructionType.JJAL:
        n = new_offset & 0x1FFFFF
        imm = format(n, '021b')
        new_bin = (imm[0] + imm[10:20] + imm[9] + imm[1:9] + b[20:25] + b[25:])
        return InstructionDetails(format(int(new_bin, 2), '08x'))
    return inst


def _run(
    instructions: list[InstructionDetails],
    compute_data_nops,
    control_nops: int,
    base_addr: int,
) -> list[InstructionRow]:
    # Função principal que processa todas as instruções e insere os NOPs necessários.
    # Funciona em duas etapas:
    #   1ª passagem: insere NOPs de dados (via compute_data_nops) e de controle (após branches)
    #   2ª passagem: corrige os endereços de todos os desvios que foram deslocados pelos NOPs

    # Controla quando cada registrador fica disponível para leitura (sem forwarding)
    reg_avail = [0] * 32
    # Mesma ideia, mas só para loads — usado para detectar load-use com forwarding
    reg_load_avail = [0] * 32

    # Guarda a posição de cada instrução original na nova sequência (já com NOPs)
    # Isso serve para recalcular os offsets dos desvios depois
    original_to_new: dict[int, int] = {}
    raw: list[tuple[InstructionDetails, bool, Optional[int]]] = []

    for orig_idx, inst in enumerate(instructions):
        # Quantos NOPs de dados precisam vir antes desta instrução?
        nops = compute_data_nops(reg_avail, reg_load_avail, inst, len(raw))
        for _ in range(nops):
            raw.append((make_nop(), True, None))

        original_to_new[orig_idx] = len(raw)
        raw.append((inst, False, orig_idx))

        # Atualiza quando o rd dessa instrução vai estar disponível
        rd = _get_rd(inst)
        if rd is not None:
            # Sem forwarding: o valor só fica pronto depois do WB (3 instruções de distância)
            reg_avail[rd] = len(raw) + 3
            if inst.type in LOAD_TYPES:
                # Load-use: mesmo com forwarding, o dado do lw ainda chega 1 ciclo tarde
                reg_load_avail[rd] = len(raw) + 1
            else:
                reg_load_avail[rd] = 0

        # Se tem NOPs de controle configurados e essa é um branch/jal, insere após ela
        if control_nops and (inst.type in BRANCH_TYPES or inst.type == InstructionType.JJAL):
            for _ in range(control_nops):
                raw.append((make_nop(), True, None))

    # 2ª passagem: agora que sabemos onde cada instrução ficou, corrigimos os offsets
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
                # O alvo está dentro do bloco — calcula novo offset pela posição mapeada
                new_target_idx = original_to_new[orig_target_idx]
                new_off = (new_target_idx - new_idx) * 4
            else:
                # O alvo é externo ao bloco — mantém o endereço absoluto e recalcula o offset
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


# ── Sequência de demonstração ──────────────────────────────────────────────────
# Funções auxiliares para montar instruções na mão, usadas só na aba Demo da interface

def _encode_r(rd: int, rs1: int, rs2: int, funct3: int = 0, funct7: int = 0) -> str:
    # Monta o hex de uma instrução tipo R (add, sub, and, or...)
    v = (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0110011
    return format(v, '08x')


def _encode_lw(rd: int, rs1: int, imm: int = 0) -> str:
    # Monta o hex de um lw
    v = ((imm & 0xFFF) << 20) | (rs1 << 15) | (0b010 << 12) | (rd << 7) | 0b0000011
    return format(v, '08x')


def _encode_beq(rs1: int, rs2: int, offset: int) -> str:
    # Monta o hex de um beq com o offset desejado
    b12   = (offset >> 12) & 1
    b11   = (offset >> 11) & 1
    b10_5 = (offset >> 5) & 0x3F
    b4_1  = (offset >> 1) & 0xF
    v = ((b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15)
         | (b4_1 << 8) | (b11 << 7) | 0b1100011)
    return format(v, '08x')


def create_demo_sequence() -> list[InstructionDetails]:
    # Sequência criada manualmente para a aba Demo, com todos os tipos de hazard presentes:
    #
    # 0: add  x1, x2, x3   → escreve x1
    # 1: add  x4, x1, x5   → lê x1 logo após a escrita → RAW hazard
    # 2: add  x6, x4, x7   → lê x4 logo após a escrita → RAW hazard
    # 3: lw   x8, 0(x6)    → lê x6 (RAW) + é um load
    # 4: add  x9, x8, x1   → lê x8 que acabou de ser carregado → load-use hazard
    # 5: beq  x1, x4, +8   → desvio para instrução 7 → hazard de controle
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


# ── Inserção de NOPs ───────────────────────────────────────────────────────────

def insert_nops_no_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Sem forwarding: o valor de rd só fica disponível depois do WB (estágio 5).
    # Isso significa que pode precisar de até 3 NOPs entre a escrita e a leitura.
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
    # Com forwarding: a maioria dos conflitos RAW desaparece porque o valor é repassado
    # direto entre os estágios (EX→EX e MEM→EX). O único caso que ainda precisa de NOP
    # é o load-use: o lw só tem o dado no MEM, depois que o leitor já passou pelo EX.
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
    # Conflito de controle sem forwarding de dados.
    # O endereço do desvio só é conhecido no EX (ciclo 3), então 2 instruções
    # já foram buscadas sem necessidade — por isso inserimos 2 NOPs após cada branch/jal.
    return _run(instructions, lambda *_: 0, 2, base_addr)


def insert_nops_control_hazard_with_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Conflito de controle com forwarding de dados.
    # Forwarding não resolve conflito de controle — o problema é saber para onde ir,
    # não a disponibilidade de um registrador. Por isso os 2 NOPs continuam necessários.
    return _run(instructions, lambda *_: 0, 2, base_addr)


def insert_nops_integrated_no_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    # Solução integrada sem forwarding: resolve dados e controle de uma vez só.
    # Dados: até 3 NOPs por RAW | Controle: 2 NOPs após cada branch/jal
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
    # Solução integrada com forwarding: resolve dados e controle de uma vez só.
    # Dados: só load-use ainda precisa de NOP (1 NOP) | Controle: 2 NOPs após cada branch/jal
    def compute(_avail, reg_load_avail, inst, pos):
        rs1, rs2 = _get_rs1(inst), _get_rs2(inst)
        n = 0
        if rs1 and rs1 != 0:
            n = max(n, reg_load_avail[rs1] - pos)
        if rs2 and rs2 != 0:
            n = max(n, reg_load_avail[rs2] - pos)
        return max(0, n)

    return _run(instructions, compute, 2, base_addr)


# ── Detecção de hazards ────────────────────────────────────────────────────────

def detect_data_hazards_no_forwarding(instructions: list[InstructionDetails]) -> list[HazardReport]:
    # Sem forwarding, qualquer instrução que lê um registrador que foi escrito
    # nas 3 anteriores causa RAW hazard. Quanto mais perto a escrita, mais NOPs precisam:
    #   dist=1 → 3 NOPs | dist=2 → 2 NOPs | dist=3 → 1 NOP
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
    # Com forwarding, os conflitos RAW normais desaparecem. O único que sobra é o load-use:
    # quando um lw é seguido direto por uma instrução que usa o registrador carregado.
    # Isso acontece porque o lw só tem o dado no MEM, que é tarde demais pro próximo EX.
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
    # Todo branch (beq, bne...) e todo jal causam conflito de controle.
    # O pipeline já foi com 2 instruções quando o desvio é resolvido no EX,
    # então sempre precisará de 2 NOPs para corrigir.
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


def detect_control_hazards_with_forwarding(instructions: list[InstructionDetails]) -> list[HazardReport]:
    # Forwarding de dados não ajuda no conflito de controle — o problema não é um
    # registrador atrasado, é não saber para qual endereço pular. O resultado é igual.
    return detect_control_hazards(instructions)


# ── Geração de arquivo de saída ───────────────────────────────────────────────

def write_rows_to_file(rows: list[InstructionRow], filename: str) -> None:
    # Salva a sequência de instruções (com NOPs já inseridos) num arquivo de texto.
    # Cada linha é uma instrução em hexadecimal, no mesmo formato do dump do RARS.
    with open(filename, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(row.inst.hexInstruction.lower() + '\n')

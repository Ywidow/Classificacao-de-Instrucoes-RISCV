from dataclasses import dataclass, field
from typing import Optional

from Domain.Entities.InstructionDetails import InstructionDetails
from Domain.Enums.InstructionType import InstructionType
from Domain.Enums.OpCode import OpCode

NOP_HEX = '00000013'

LOAD_TYPES = frozenset({
    InstructionType.ILB, InstructionType.ILH, InstructionType.ILW,
    InstructionType.ILBU, InstructionType.ILHU,
})

BRANCH_TYPES = frozenset({
    InstructionType.BBEQ, InstructionType.BBNE, InstructionType.BBLT,
    InstructionType.BBGE, InstructionType.BBLTU, InstructionType.BBGEU,
})

# Opcodes whose instructions write to Rd
WRITES_RD_OPCODES = frozenset({
    OpCode.U0110111, OpCode.U0010111, OpCode.J1101111, OpCode.I1100111,
    OpCode.I0000011, OpCode.I0010011, OpCode.R0110011,
})

# Opcodes whose instructions read Rs1
READS_RS1_OPCODES = frozenset({
    OpCode.I1100111, OpCode.B1100011, OpCode.I0000011, OpCode.S0100011,
    OpCode.I0010011, OpCode.R0110011,
})

# Opcodes whose instructions read Rs2
READS_RS2_OPCODES = frozenset({
    OpCode.B1100011, OpCode.S0100011, OpCode.R0110011,
})


@dataclass
class InstructionRow:
    inst: InstructionDetails
    is_nop: bool
    original_idx: Optional[int]  # None for inserted NOPs
    note: str = ""


def make_nop() -> InstructionDetails:
    return InstructionDetails(NOP_HEX)


def _get_rd(inst: InstructionDetails) -> Optional[int]:
    if inst.opCode not in WRITES_RD_OPCODES:
        return None
    rd = int(inst.binInstruction[20:25], 2)
    return rd if rd != 0 else None  # x0 writes are irrelevant


def _get_rs1(inst: InstructionDetails) -> Optional[int]:
    if inst.opCode in READS_RS1_OPCODES:
        return int(inst.binInstruction[12:17], 2)
    return None


def _get_rs2(inst: InstructionDetails) -> Optional[int]:
    if inst.opCode in READS_RS2_OPCODES:
        return int(inst.binInstruction[7:12], 2)
    return None


def _get_branch_offset(inst: InstructionDetails) -> int:
    """Return signed byte offset for B-type or J-type (JAL) instructions."""
    b = inst.binInstruction
    if inst.type in BRANCH_TYPES:
        # B-type: {imm[12], imm[11], imm[10:5], imm[4:1], 0}
        bits = b[0] + b[24] + b[1:7] + b[20:24] + '0'
        val = int(bits, 2)
        if b[0] == '1':
            val -= (1 << 13)
        return val
    if inst.type == InstructionType.JJAL:
        # J-type: {imm[20], imm[19:12], imm[11], imm[10:1], 0}
        bits = b[0] + b[12:20] + b[11] + b[1:11] + '0'
        val = int(bits, 2)
        if b[0] == '1':
            val -= (1 << 21)
        return val
    return 0


def _encode_with_new_offset(inst: InstructionDetails, new_offset: int) -> InstructionDetails:
    """Return a new instruction with updated branch/jump offset."""
    b = inst.binInstruction
    if inst.type in BRANCH_TYPES:
        n = new_offset & 0x1FFF
        imm = format(n, '013b')
        # bit31=imm[12], bits30:25=imm[10:5], bits11:8=imm[4:1], bit7=imm[11]
        new_bin = (imm[0] + imm[2:8] + b[7:12] + b[12:17] + b[17:20]
                   + imm[8:12] + imm[1] + b[25:])
        return InstructionDetails(format(int(new_bin, 2), '08x'))
    if inst.type == InstructionType.JJAL:
        n = new_offset & 0x1FFFFF
        imm = format(n, '021b')
        # bit31=imm[20], bits30:21=imm[10:1], bit20=imm[11], bits19:12=imm[19:12]
        new_bin = (imm[0] + imm[10:20] + imm[9] + imm[1:9] + b[20:25] + b[25:])
        return InstructionDetails(format(int(new_bin, 2), '08x'))
    return inst


def _run(
    instructions: list[InstructionDetails],
    compute_data_nops,
    control_nops: int,
    base_addr: int,
) -> list[InstructionRow]:
    """
    Core engine: insert NOPs then recalculate branch offsets.

    compute_data_nops(reg_avail, reg_load_avail, inst, current_pos) -> int
    control_nops: NOPs to insert after each branch/jump (0 = skip)
    """
    reg_avail = [0] * 32       # earliest new-seq position that can safely read this reg (no-fwd)
    reg_load_avail = [0] * 32  # same, but only updated for loads (forwarding case)

    original_to_new: dict[int, int] = {}
    raw: list[tuple[InstructionDetails, bool, Optional[int]]] = []

    for orig_idx, inst in enumerate(instructions):
        nops = compute_data_nops(reg_avail, reg_load_avail, inst, len(raw))
        for _ in range(nops):
            raw.append((make_nop(), True, None))

        original_to_new[orig_idx] = len(raw)
        raw.append((inst, False, orig_idx))

        rd = _get_rd(inst)
        if rd is not None:
            # Writer at position p; WB completes at end of cycle p+4.
            # Reader's ID is at cycle q+1 → need q+1 > p+4 → q >= p+4.
            reg_avail[rd] = len(raw) + 3          # = p+1+3 = p+4
            if inst.type in LOAD_TYPES:
                reg_load_avail[rd] = len(raw) + 1  # load-use: need q >= p+2
            else:
                reg_load_avail[rd] = 0

        if control_nops and (inst.type in BRANCH_TYPES or inst.type == InstructionType.JJAL):
            for _ in range(control_nops):
                raw.append((make_nop(), True, None))

    # Recalculate branch/jump offsets
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
                new_target_idx = original_to_new[orig_target_idx]
                new_off = (new_target_idx - new_idx) * 4
            else:
                orig_target_addr = base_addr + orig_idx * 4 + old_off
                new_branch_addr = base_addr + new_idx * 4
                new_off = orig_target_addr - new_branch_addr

            if new_off != old_off:
                note = f"Endereço desvio: {old_off:+d} → {new_off:+d} bytes"
                updated = _encode_with_new_offset(inst, new_off)
            else:
                note = f"Endereço desvio: {old_off:+d} bytes (sem mudança)"

        rows.append(InstructionRow(updated, False, orig_idx, note))

    return rows


# ── Demo sequence ─────────────────────────────────────────────────────────────

def _encode_r(rd: int, rs1: int, rs2: int, funct3: int = 0, funct7: int = 0) -> str:
    v = (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0110011
    return format(v, '08x')


def _encode_lw(rd: int, rs1: int, imm: int = 0) -> str:
    v = ((imm & 0xFFF) << 20) | (rs1 << 15) | (0b010 << 12) | (rd << 7) | 0b0000011
    return format(v, '08x')


def _encode_beq(rs1: int, rs2: int, offset: int) -> str:
    b12   = (offset >> 12) & 1
    b11   = (offset >> 11) & 1
    b10_5 = (offset >> 5) & 0x3F
    b4_1  = (offset >> 1) & 0xF
    v = ((b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15)
         | (b4_1 << 8) | (b11 << 7) | 0b1100011)
    return format(v, '08x')


def create_demo_sequence() -> list[InstructionDetails]:
    """
    Sequence designed to show all three hazard types:

    0: add  x1, x2,  x3   — writes x1
    1: add  x4, x1,  x5   — RAW: reads x1 (written at 0)   ← data hazard
    2: add  x6, x4,  x7   — RAW: reads x4 (written at 1)   ← data hazard
    3: lw   x8, 0(x6)     — RAW: reads x6 (written at 2)   ← data hazard
    4: add  x9, x8,  x1   — load-use: reads x8 (loaded at 3) ← load-use hazard
    5: beq  x1, x4,  +8   — control hazard; target = instr 7
    6: add  x10, x2, x3   — may be skipped (branch delay slot)
    7: add  x11, x1, x4   — branch target; reads x1, x4
    """
    hexes = [
        _encode_r(1, 2, 3),           # add  x1,  x2, x3
        _encode_r(4, 1, 5),           # add  x4,  x1, x5   RAW on x1
        _encode_r(6, 4, 7),           # add  x6,  x4, x7   RAW on x4
        _encode_lw(8, 6, 0),          # lw   x8,  0(x6)    RAW on x6
        _encode_r(9, 8, 1),           # add  x9,  x8, x1   load-use x8
        _encode_beq(1, 4, 8),         # beq  x1,  x4, +8   control hazard
        _encode_r(10, 2, 3),          # add  x10, x2, x3
        _encode_r(11, 1, 4),          # add  x11, x1, x4   branch target
    ]
    return [InstructionDetails(h) for h in hexes]


# ── Public API ────────────────────────────────────────────────────────────────

def insert_nops_no_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    """Insert NOPs to solve data hazards without forwarding (up to 3 NOPs per hazard)."""
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
    """Insert NOPs to solve data hazards with full forwarding (only load-use needs 1 NOP)."""
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
    """Insert 2 NOPs after every branch/jump to solve control hazards."""
    return _run(instructions, lambda *_: 0, 2, base_addr)


def insert_nops_integrated_no_forwarding(
    instructions: list[InstructionDetails], base_addr: int = 0
) -> list[InstructionRow]:
    """Solução integrada: dados sem forwarding (até 3 NOPs por RAW) + controle (2 NOPs após desvio)."""
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
    """Solução integrada: dados com forwarding (1 NOP load-use) + controle (2 NOPs após desvio)."""
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

@dataclass
class HazardReport:
    instr_idx: int
    description: str


def detect_data_hazards_no_forwarding(instructions: list[InstructionDetails]) -> list[HazardReport]:
    """
    Detecta conflitos RAW sem forwarding.
    Sem forwarding, o escritor precisa completar WB antes do leitor fazer ID.
    Distância mínima = 4 instruções → distâncias 1, 2 e 3 geram hazard.
    """
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
    """
    Detecta conflitos RAW com forwarding.
    Com forwarding EX-EX e MEM-EX, apenas load-use (lw seguido imediatamente de leitura) requer 1 NOP.
    """
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
                f"[Instr {i}] Load-use hazard: x{rd} ({', '.join(regs)}), 1 NOP necessário"
            ))
    return reports


def detect_control_hazards(instructions: list[InstructionDetails]) -> list[HazardReport]:
    """
    Detecta conflitos de controle (desvios e saltos).
    O desvio é resolvido no estágio EX (ciclo 3), portanto 2 instruções já entraram → 2 NOPs necessários.
    """
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
    """Grava a sequência de instruções (hexadecimal) em um arquivo texto."""
    with open(filename, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(row.inst.hexInstruction.lower() + '\n')

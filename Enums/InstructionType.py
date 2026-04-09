from enum import Enum

class InstructionType(Enum):
    ULUI = ("0110111", "U lui")
    UAUIPC = ("0010111", "U auipc")
    JJAL = ("1101111", "J jal")
    IJALR = ("1100111", "I jalr")
    BBEQ = ("1100011", "B beq")
    BBNE = ("1100011", "B bne")
    BBLT = ("1100011", "B blt")
    BBGE = ("1100011", "B bge")
    BBLTU = ("1100011", "B bltu")
    BBGEU = ("1100011", "B bgeu")

    ILB = ("0000011", "I lb")
    ILH = ("0000011", "I lh")
    ILW = ("0000011", "I lw")
    ILBU = ("0000011", "I lbu")
    ILHU = ("0000011", "I lhu")

    SSB = ("0100011", "S sb")
    SSH = ("0100011", "S sh")
    SSW = ("0100011", "S sw")

    IADDI = ("0010011", "I addi")
    ISLTI = ("0010011", "I slti")
    ISLTIU = ("0010011", "I sltiu")
    IXORI = ("0010011", "I xori")
    IORI = ("0010011", "I ori")
    IANDI = ("0010011", "I andi")
    ISLLI = ("0010011", "I slli")
    ISRLI = ("0010011", "I srli")
    ISRAI = ("0010011", "I srai")

    RADD = ("0110011", "R add")
    RSUB = ("0110011", "R sub")
    RSLL = ("0110011", "R sll")
    RSLT = ("0110011", "R slt")
    RSLTU = ("0110011", "R sltu")
    RXOR = ("0110011", "R xor")
    RSRL = ("0110011", "R srl")
    RSRA = ("0110011", "R sra")
    ROR = ("0110011", "R or")
    RAND = ("0110011", "R and")

    IFENCE = ("0001111", "I fence")
    IFENCE_I = ("0001111", "I fence.i")

    IECALL = ("1110011", "I ecall")
    IEBREAK = ("1110011", "I ebreak")
    ICSRRW = ("1110011", "I csrrw")
    ICSRRS = ("1110011", "I csrrs")
    ICSRRC = ("1110011", "I csrrc")
    ICSRRWI = ("1110011", "I csrrwi")
    ICSRRSI = ("1110011", "I csrrsi")
    ICSRRCI = ("1110011", "I csrrci")

    def __init__(self, opcode: str, instr_type: str):
        self.opcode = opcode
        self.instr_type = instr_type
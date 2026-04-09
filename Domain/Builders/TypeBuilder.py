from Domain.Enums.InstructionType import InstructionType
from Domain.Enums.OpCode import OpCode

def defineTypeForInstruction(opCode: OpCode, binInstruction: str) -> InstructionType:
    match opCode:
        case OpCode.U0110111:
            return InstructionType.ULUI
        case OpCode.U0010111:
            return InstructionType.UAUIPC
        case OpCode.J1101111:
            return InstructionType.JJAL
        case OpCode.I1100111:
            return InstructionType.IJALR
        case OpCode.B1100011:
            return handleTypeWhenOpCodeIsB1100011(binInstruction)
        case OpCode.I0000011:
            return handleTypeWhenOpCodeIsI0000011(binInstruction)
        case OpCode.S0100011:
            return handleTypeWhenOpCodeIsS0100011(binInstruction)
        case OpCode.I0010011:
            return handleTypeWhenOpCodeIsI0010011(binInstruction)
        case OpCode.R0110011:
            return handleTypeWhenOpCodeIsR0110011(binInstruction)
        case OpCode.I0001111:
            return handleTypeWhenOpCodeIsI0001111(binInstruction)
        case OpCode.I1110011:
            return handleTypeWhenOpCodeIsI1110011(binInstruction)
        case _:
            raise Exception(
                f"Não foi possível definir uma instrução com opCode = {opCode} e binInstruction = {binInstruction}")

def handleTypeWhenOpCodeIsB1100011(binInstruction) -> InstructionType:
    identifier = binInstruction[17:20]

    match identifier:
        case '000':
            return InstructionType.BBEQ
        case '001':
            return InstructionType.BBNE
        case '100':
            return InstructionType.BBLT
        case '101':
            return InstructionType.BBGE
        case '110':
            return InstructionType.BBLTU
        case '111':
            return InstructionType.BBGEU
        case _:
            raise Exception(f"B1100011 identifier = {identifier} não é válido")

def handleTypeWhenOpCodeIsI0000011(binInstruction) -> InstructionType:
    identifier = binInstruction[17:20]

    match identifier:
        case '000':
            return InstructionType.ILB
        case '001':
            return InstructionType.ILH
        case '010':
            return InstructionType.ILW
        case '100':
            return InstructionType.ILBU
        case '101':
            return InstructionType.ILHU
        case _:
            raise Exception(f"I0000011 identifier = {identifier} não é válido")

def handleTypeWhenOpCodeIsS0100011(binInstruction) -> InstructionType:
    identifier = binInstruction[17:20]

    match identifier:
        case '000':
            return InstructionType.SSB
        case '001':
            return InstructionType.SSH
        case '010':
            return InstructionType.SSW
        case _:
            raise Exception(f"S0100011 identifier = {identifier} não é válido")

def handleTypeWhenOpCodeIsI0010011(binInstruction) -> InstructionType:
    identifier = binInstruction[17:20]

    match identifier:
        case '000':
            return InstructionType.IADDI
        case '010':
            return InstructionType.ISLTI
        case '011':
            return InstructionType.ISLTIU
        case '100':
            return InstructionType.IXORI
        case '110':
            return InstructionType.IORI
        case '111':
            return InstructionType.IANDI
        case '001':
            return InstructionType.ISLLI
        case '101':
            funct7 = binInstruction[1:8]
            if '1' not in funct7:
                return InstructionType.ISRLI
            return InstructionType.ISRAI
        case _:
            raise Exception(f"I0010011 identifier = {identifier} não é válido")

def handleTypeWhenOpCodeIsR0110011(binInstruction) -> InstructionType:
    identifier = binInstruction[17:20]

    match identifier:
        case '000':
            funct7 = binInstruction[1:8]
            if '1' not in funct7:
                return InstructionType.RADD
            return InstructionType.RSUB
        case '001':
            return InstructionType.RSLL
        case '010':
            return InstructionType.RSLT
        case '011':
            return InstructionType.RSLTU
        case '100':
            return InstructionType.RXOR
        case '101':
            funct7 = binInstruction[1:8]
            if '1' not in funct7:
                return InstructionType.RSRL
            return InstructionType.RSRA
        case '110':
            return InstructionType.ROR
        case '111':
            return InstructionType.RAND
        case _:
            raise Exception(f"R0110011 identifier = {identifier} não é válido")

def handleTypeWhenOpCodeIsI0001111(binInstruction) -> InstructionType:
    identifier = binInstruction[17:20]

    match identifier:
        case '000':
            return InstructionType.IFENCE
        case '001':
            return InstructionType.IFENCE_I
        case _:
            raise Exception(f"I0001111 identifier = {identifier} não é válido")

def handleTypeWhenOpCodeIsI1110011(binInstruction) -> InstructionType:
    identifier = binInstruction[17:20]

    match identifier:
        case '000':
            funct7 = binInstruction[1:13]
            if '1' not in funct7:
                return InstructionType.IECALL
            return InstructionType.IEBREAK
        case '001':
            return InstructionType.ICSRRW
        case '010':
            return InstructionType.ICSRRS
        case '011':
            return InstructionType.ICSRRC
        case '101':
            return InstructionType.ICSRRWI
        case '110':
            return InstructionType.ICSRRSI
        case '111':
            return InstructionType.ICSRRCI
        case _:
            raise Exception(f"I1110011 identifier = {identifier} não é válido")
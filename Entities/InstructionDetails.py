from dataclasses import dataclass

from Enums.InstructionType import InstructionType
from Enums.OpCode import OpCode

@dataclass
class InstructionDetails:
    hexInstruction: str
    binInstruction: str
    opCode: OpCode
    type: InstructionType
    specificProperties: dict[str, str]

    def __init__(self, hexInstruction: str):
        self.hexInstruction = hexInstruction
        self.binInstruction = self.setBinInstruction(hexInstruction)
        self.opCode = self.setOpCode()
        self.type = self.setType()
        self.specificProperties = {}

        self.setSpecificProperties()

    @staticmethod
    def setBinInstruction(hexInstruction: str) -> str:
        return format(int(hexInstruction, 16), "032b")

    def setOpCode(self) -> OpCode:
        return OpCode(self.binInstruction[-7:])

    def setType(self) -> InstructionType:
        match self.opCode:
            case OpCode.U0110111:
                return InstructionType.ULUI
            case OpCode.U0010111:
                return InstructionType.UAUIPC
            case OpCode.J1101111:
                return InstructionType.JJAL
            case OpCode.I1100111:
                return InstructionType.IJALR
            case OpCode.B1100011:
                return self.handleTypeWhenOpCodeIsB1100011()
            case OpCode.I0000011:
                return self.handleTypeWhenOpCodeIsI0000011()
            case OpCode.S0100011:
                return self.handleTypeWhenOpCodeIsS0100011()
            case OpCode.I0010011:
                return self.handleTypeWhenOpCodeIsI0010011()
            case OpCode.R0110011:
                return self.handleTypeWhenOpCodeIsR0110011()
            case OpCode.I0001111:
                return self.handleTypeWhenOpCodeIsI0001111()
            case OpCode.I1110011:
                return self.handleTypeWhenOpCodeIsI1110011()
            case _:
                raise Exception(f"OpCode = {self.opCode} não é válido")

    def setSpecificProperties(self):
        if self.type is InstructionType.ULUI or self.type is InstructionType.UAUIPC:
            self.setSpecificPropertiesForUpperImmediate()
            return

        if self.type is InstructionType.JJAL:
            self.setSpecificPropertiesForJump()
            return

        if self.instructionContainsTwelveBitsInImm():
            self.setSpecificPropertiesForInstructionsWithTwelveBitsImmediate()
            return

        if self.opCode is OpCode.B1100011:
            self.setSpecificPropertiesForBranch()
            return

        if self.opCode is OpCode.S0100011:
            self.setSpecificPropertiesForStore()
            return

        if self.instructionIsImmediateWithShamt():
            self.setSpecificPropertiesForImmediatesWithShamt()
            return

        if self.opCode is OpCode.R0110011:
            self.setSpecificPropertiesForRegisters()
            return

        if self.type is InstructionType.IFENCE:
            self.setSpecificPropertiesForIFence()
            return

        if self.instructionIsImmediateWithCsrAndRs1():
            self.setSpecificPropertiesForImmediateWithCsrAndRs1()
            return

        if self.instructionIsImmediateWithCsrAndZimm():
            self.setSpecificPropertiesForImmediateWithCsrAndZimm()
            return

    def instructionContainsTwelveBitsInImm(self):
        return (self.opCode is OpCode.I1100111
            or self.opCode is OpCode.I0000011
            or self.type is InstructionType.IADDI
            or self.type is InstructionType.ISLTI
            or self.type is InstructionType.ISLTIU
            or self.type is InstructionType.IXORI
            or self.type is InstructionType.IORI
            or self.type is InstructionType.IANDI)

    def instructionIsImmediateWithShamt(self):
        return (self.type is InstructionType.ISLLI
            or self.type is InstructionType.ISRLI
            or self.type is InstructionType.ISRAI)

    def instructionIsImmediateWithCsrAndRs1(self):
        return (self.type is InstructionType.ICSRRW
            or self.type is InstructionType.ICSRRS
            or self.type is InstructionType.ICSRRC)

    def instructionIsImmediateWithCsrAndZimm(self):
        return (self.type is InstructionType.ICSRRWI
            or self.type is InstructionType.ICSRRSI
            or self.type is InstructionType.ICSRRCI)

    def print(self):
        print(f'Instrução em Hexadecimal: {self.hexInstruction}'
              f'\nInstrução em Binário: {self.binInstruction}'
              f'\nOpCode: {self.opCode.value}'
              f'\nTipo: {self.type.instr_type}'
              f'{self.printSpecificProperties()}'
              f'\n')

    def printSpecificProperties(self) -> str:
        text = ''
        for value in self.specificProperties:
            text += f'\n{value}: {self.specificProperties[value]}'
        return text

    # Handlers for type based on OpCode
    def handleTypeWhenOpCodeIsB1100011(self) -> InstructionType:
        identifier = self.binInstruction[17:20]

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

    def handleTypeWhenOpCodeIsI0000011(self) -> InstructionType:
        identifier = self.binInstruction[17:20]

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

    def handleTypeWhenOpCodeIsS0100011(self) -> InstructionType:
        identifier = self.binInstruction[17:20]

        match identifier:
            case '000':
                return InstructionType.SSB
            case '001':
                return InstructionType.SSH
            case '010':
                return InstructionType.SSW
            case _:
                raise Exception(f"S0100011 identifier = {identifier} não é válido")

    def handleTypeWhenOpCodeIsI0010011(self) -> InstructionType:
        identifier = self.binInstruction[17:20]

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
                funct7 = self.binInstruction[1:8]
                if '1' not in funct7:
                    return InstructionType.ISRLI
                return InstructionType.ISRAI
            case _:
                raise Exception(f"I0010011 identifier = {identifier} não é válido")

    def handleTypeWhenOpCodeIsR0110011(self) -> InstructionType:
        identifier = self.binInstruction[17:20]

        match identifier:
            case '000':
                funct7 = self.binInstruction[1:8]
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
                funct7 = self.binInstruction[1:8]
                if '1' not in funct7:
                    return InstructionType.RSRL
                return InstructionType.RSRA
            case '110':
                return InstructionType.ROR
            case '111':
                return InstructionType.RAND
            case _:
                raise Exception(f"R0110011 identifier = {identifier} não é válido")

    def handleTypeWhenOpCodeIsI0001111(self) -> InstructionType:
        identifier = self.binInstruction[17:20]

        match identifier:
            case '000':
                return InstructionType.IFENCE
            case '001':
                return InstructionType.IFENCE_I
            case _:
                raise Exception(f"I0001111 identifier = {identifier} não é válido")

    def handleTypeWhenOpCodeIsI1110011(self) -> InstructionType:
        identifier = self.binInstruction[17:20]

        match identifier:
            case '000':
                funct7 = self.binInstruction[1:13]
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

    # Handlers to set specifics properties
    def setRd(self):
        self.specificProperties['Rd'] = f'{self.binInstruction[20:25]} ({int(self.binInstruction[20:25], 2)})'

    def setRs1(self):
        self.specificProperties['Rs1'] = f'{self.binInstruction[12:17]} ({int(self.binInstruction[12:17], 2)})'

    def setRs2(self):
        self.specificProperties['Rs2'] = f'{self.binInstruction[7:12]} ({int(self.binInstruction[7:12], 2)})'

    def setCsr(self):
        self.specificProperties['Csr'] = f'{self.binInstruction[0:12]} ({int(self.binInstruction[0:12], 2)})'

    def setSpecificPropertiesForUpperImmediate(self):
        self.specificProperties['Imm'] = f'{self.binInstruction[0:20]} ({int(self.binInstruction[0:20], 2)})'
        self.setRd()

    def setSpecificPropertiesForJump(self):
        imm = (f'{self.binInstruction[11]}'
            f'{self.binInstruction[21:32]}'
            f'{self.binInstruction[20]}'
            f'{self.binInstruction[12:20]}')
        self.specificProperties['Imm'] = f'{imm} ({int(imm, 2)})'
        self.setRd()

    def setSpecificPropertiesForInstructionsWithTwelveBitsImmediate(self):
        self.specificProperties['Imm'] = f'{self.binInstruction[20:]} ({int(self.binInstruction[20:], 2)})'
        self.setRs1()
        self.setRd()

    def setSpecificPropertiesForBranch(self):
        imm1 = f'{self.binInstruction[19]}{self.binInstruction[21:27]}'
        self.specificProperties['Imm 1'] = f'{imm1} ({int(imm1, 2)})'
        self.setRs2()
        self.setRs1()
        imm2 = f'{self.binInstruction[27:31]}{self.binInstruction[20]}'
        self.specificProperties['Imm 2'] = f'{imm2} ({int(imm2, 2)})'

    def setSpecificPropertiesForStore(self):
        imm1 = self.binInstruction[20:27]
        self.specificProperties['Imm 1'] = f'{imm1} ({int(imm1, 2)})'
        self.setRs2()
        self.setRs1()
        imm2 = self.binInstruction[27:]
        self.specificProperties['Imm 2'] = f'{imm2} ({int(imm2, 2)})'

    def setSpecificPropertiesForImmediatesWithShamt(self):
        self.specificProperties['Shamt'] = f'{self.binInstruction[7:12]} ({int(self.binInstruction[7:12], 2)})'
        self.setRs1()
        self.setRd()

    def setSpecificPropertiesForRegisters(self):
        self.setRs2()
        self.setRs1()
        self.setRd()

    def setSpecificPropertiesForIFence(self):
        self.specificProperties['Pred'] = f'{self.binInstruction[4:8]} ({int(self.binInstruction[4:8], 2)})'
        self.specificProperties['Succ'] = f'{self.binInstruction[8:12]} ({int(self.binInstruction[8:12], 2)})'

    def setSpecificPropertiesForImmediateWithCsrAndRs1(self):
        self.setCsr()
        self.setRs1()
        self.setRd()

    def setSpecificPropertiesForImmediateWithCsrAndZimm(self):
        self.setCsr()
        self.specificProperties['Zimm'] = f'{self.binInstruction[12:17]} ({int(self.binInstruction[12:17], 2)})'
        self.setRd()
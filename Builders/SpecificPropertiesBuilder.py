from dataclasses import dataclass

from Enums.InstructionType import InstructionType
from Enums.OpCode import OpCode

@dataclass
class SpecificPropertiesBuilder:
    type: InstructionType
    opCode: OpCode
    binInstruction: str
    specificProperties: dict[str, str]

    def __init__(self, type: InstructionType, opCode: OpCode, binInstruction: str):
        self.type = type
        self.opCode = opCode
        self.binInstruction = binInstruction
        self.specificProperties = {}

    def buildSpecificProperties(self) -> dict[str, str]:
        if self.type is InstructionType.ULUI or self.type is InstructionType.UAUIPC:
            self.setSpecificPropertiesForUpperImmediate()
            return self.specificProperties

        if self.type is InstructionType.JJAL:
            self.setSpecificPropertiesForJump()
            return self.specificProperties

        if self.instructionContainsTwelveBitsInImm():
            self.setSpecificPropertiesForInstructionsWithTwelveBitsImmediate()
            return self.specificProperties

        if self.opCode is OpCode.B1100011:
            self.setSpecificPropertiesForBranch()
            return self.specificProperties

        if self.opCode is OpCode.S0100011:
            self.setSpecificPropertiesForStore()
            return self.specificProperties

        if self.instructionIsImmediateWithShamt():
            self.setSpecificPropertiesForImmediatesWithShamt()
            return self.specificProperties

        if self.opCode is OpCode.R0110011:
            self.setSpecificPropertiesForRegisters()
            return self.specificProperties

        if self.type is InstructionType.IFENCE:
            self.setSpecificPropertiesForIFence()
            return self.specificProperties

        if self.instructionIsImmediateWithCsrAndRs1():
            self.setSpecificPropertiesForImmediateWithCsrAndRs1()
            return self.specificProperties

        if self.instructionIsImmediateWithCsrAndZimm():
            self.setSpecificPropertiesForImmediateWithCsrAndZimm()
            return self.specificProperties

        return self.specificProperties

    def instructionContainsTwelveBitsInImm(self) -> bool:
        return (self.opCode is OpCode.I1100111
            or self.opCode is OpCode.I0000011
            or self.type is InstructionType.IADDI
            or self.type is InstructionType.ISLTI
            or self.type is InstructionType.ISLTIU
            or self.type is InstructionType.IXORI
            or self.type is InstructionType.IORI
            or self.type is InstructionType.IANDI)

    def instructionIsImmediateWithShamt(self) -> bool:
        return (self.type is InstructionType.ISLLI
            or self.type is InstructionType.ISRLI
            or self.type is InstructionType.ISRAI)

    def instructionIsImmediateWithCsrAndRs1(self) -> bool:
        return (self.type is InstructionType.ICSRRW
            or self.type is InstructionType.ICSRRS
            or self.type is InstructionType.ICSRRC)

    def instructionIsImmediateWithCsrAndZimm(self) -> bool:
        return (self.type is InstructionType.ICSRRWI
            or self.type is InstructionType.ICSRRSI
            or self.type is InstructionType.ICSRRCI)

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
        self.specificProperties['Imm']= f'{self.binInstruction[20:]} ({int(self.binInstruction[20:], 2)})'
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

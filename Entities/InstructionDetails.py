from dataclasses import dataclass

from Builders.SpecificPropertiesBuilder import SpecificPropertiesBuilder
from Builders.TypeBuilder import defineTypeForInstruction
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
        self.type = defineTypeForInstruction(self.opCode, self.binInstruction)
        self.specificProperties = (
            SpecificPropertiesBuilder(self.type, self.opCode, self.binInstruction).buildSpecificProperties())

    @staticmethod
    def setBinInstruction(hexInstruction: str) -> str:
        return format(int(hexInstruction, 16), "032b")

    def setOpCode(self) -> OpCode:
        return OpCode(self.binInstruction[-7:])

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

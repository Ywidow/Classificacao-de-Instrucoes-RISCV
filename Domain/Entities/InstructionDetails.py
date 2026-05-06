from dataclasses import dataclass

from Domain.Builders.SpecificPropertiesBuilder import SpecificPropertiesBuilder
from Domain.Builders.TypeBuilder import defineTypeForInstruction
from Domain.Enums.InstructionType import InstructionType
from Domain.Enums.OpCode import OpCode

@dataclass
class InstructionDetails:
    hexInstruction: str
    binInstruction: str
    opCode: OpCode
    type: InstructionType
    specificProperties: dict[str, str]

    def __init__(self, hexInstruction: str):
        # Recebe o hex e já faz toda a decodificação em sequência
        self.hexInstruction = hexInstruction
        self.binInstruction = self.setBinInstruction(hexInstruction)  # hex → binário de 32 bits
        self.opCode = self.setOpCode()                                 # pega os 7 bits do opcode
        self.type = defineTypeForInstruction(self.opCode, self.binInstruction)  # identifica a instrução (add, lw, beq...)
        self.specificProperties = (
            SpecificPropertiesBuilder(self.type, self.opCode, self.binInstruction).buildSpecificProperties())  # extrai rd, rs1, rs2, imm...

    @staticmethod
    def setBinInstruction(hexInstruction: str) -> str:
        # Converte os 8 dígitos hex para uma string de 32 bits
        return format(int(hexInstruction, 16), "032b")

    def setOpCode(self) -> OpCode:
        # No RISC-V, os 7 bits menos significativos são sempre o opcode
        # Como a string binária começa pelo MSB, o opcode fica nos últimos 7 caracteres
        return OpCode(self.binInstruction[-7:])

    def print(self):
        # Imprime tudo sobre a instrução — útil para debug
        print(f'Instrução em Hexadecimal: {self.hexInstruction}'
            f'\nInstrução em Binário: {self.binInstruction}'
            f'\nOpCode: {self.opCode.value}'
            f'\nTipo: {self.type.instr_type}'
            f'{self.printSpecificProperties()}'
            f'\n')

    def printSpecificProperties(self) -> str:
        # Formata os campos da instrução (rd, rs1, imm...) para impressão
        text = ''
        for value in self.specificProperties:
            text += f'\n{value}: {self.specificProperties[value]}'
        return text

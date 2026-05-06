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
        # Recebe o hex da instrução e já faz toda a decodificação automaticamente
        self.hexInstruction = hexInstruction
        self.binInstruction = self.setBinInstruction(hexInstruction)  # converte para binário
        self.opCode = self.setOpCode()                                 # extrai os 7 bits do opcode
        self.type = defineTypeForInstruction(self.opCode, self.binInstruction)  # identifica o tipo (add, lw, beq...)
        self.specificProperties = (
            SpecificPropertiesBuilder(self.type, self.opCode, self.binInstruction).buildSpecificProperties())  # extrai rd, rs1, rs2, imm...

    @staticmethod
    def setBinInstruction(hexInstruction: str) -> str:
        # Converte o hex de 8 dígitos para uma string de 32 bits (ex: "0x00000013" → "00000000000000000000000000010011")
        return format(int(hexInstruction, 16), "032b")

    def setOpCode(self) -> OpCode:
        # Os 7 bits menos significativos da instrução RISC-V são o opcode (bits 6:0)
        # Na string binária de 32 bits com MSB primeiro, isso corresponde aos últimos 7 caracteres
        return OpCode(self.binInstruction[-7:])

    def print(self):
        # Imprime no console todas as informações da instrução (usado para debug)
        print(f'Instrução em Hexadecimal: {self.hexInstruction}'
            f'\nInstrução em Binário: {self.binInstruction}'
            f'\nOpCode: {self.opCode.value}'
            f'\nTipo: {self.type.instr_type}'
            f'{self.printSpecificProperties()}'
            f'\n')

    def printSpecificProperties(self) -> str:
        # Formata os campos específicos (rd, rs1, imm...) como string para impressão
        text = ''
        for value in self.specificProperties:
            text += f'\n{value}: {self.specificProperties[value]}'
        return text

from Entities.InstructionDetails import InstructionDetails

def readEachLineFromFile(filename: str) -> list[str]:
    lines: list[str] = []
    with open(filename, "r", encoding="utf-8") as file:
        for line in file:
            if len(line.strip()) == 8:
                lines.append(line.strip())
                continue

            lines.append(f"{int(line.strip(), 2):08x}")

    return lines

hexInstructions = readEachLineFromFile('Instruções.txt')

instructionDetails: list[InstructionDetails] = []
for hexInstruction in hexInstructions:
    instructionDetails.append(InstructionDetails(hexInstruction))

for instructions in instructionDetails:
    instructions.print()
from Domain.Entities.InstructionDetails import InstructionDetails
from Presentation.Models.InstructionViewer import InstructionViewer

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

#for inst in instructionDetails:
#    inst.print()

ui = InstructionViewer(instructionDetails)
ui.mainloop()
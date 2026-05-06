# -*- coding: utf-8 -*-
# Trabalho M1/M2 sobre identificação de instruções e análise de hazards
# Professor: Thiago Felski
# Matéria: Organização de Computadores
# Desenvolvedores: Guilherme Thomy, Ismael Junior, Eduardo Leopoldo

import tkinter as tk
from tkinter import filedialog

from Domain.Entities.InstructionDetails import InstructionDetails
from Domain.Services.HazardAnalyzer import (
    detect_data_hazards_no_forwarding,
    detect_data_hazards_with_forwarding,
    detect_control_hazards,
    insert_nops_no_forwarding,
    insert_nops_with_forwarding,
    insert_nops_control_hazard,
    insert_nops_integrated_no_forwarding,
    insert_nops_integrated_with_forwarding,
    write_rows_to_file,
)
from Presentation.Models.InstructionViewer import InstructionViewer


def readEachLineFromFile(filename: str) -> list[str]:
    lines: list[str] = []
    with open(filename, "r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            if len(stripped) == 8:
                lines.append(stripped)
                continue
            lines.append(f"{int(stripped, 2):08x}")
    return lines


def selectFile() -> str:
    root = tk.Tk()
    root.withdraw()
    filename = filedialog.askopenfilename(
        title="Selecione o arquivo de instrucoes (hex ou binario)",
        filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")]
    )
    root.destroy()
    return filename


def main():
    filename = selectFile()
    if not filename:
        print("Nenhum arquivo selecionado, usando Instrucoes.txt")
        filename = 'Instruções.txt'

    hexInstructions = readEachLineFromFile(filename)
    instructionDetails: list[InstructionDetails] = [
        InstructionDetails(h) for h in hexInstructions
    ]
    n = len(instructionDetails)

    print(f"\nArquivo: {filename}")
    print(f"Total de instrucoes: {n}\n")

    # Deteccao de hazards
    print("--- Conflitos de dados (sem forwarding) ---")
    semFwd = detect_data_hazards_no_forwarding(instructionDetails)
    if semFwd:
        for h in semFwd:
            print(f"  {h.description}")
    else:
        print("  Nenhum conflito detectado.")

    print("\n--- Conflitos de dados (com forwarding) ---")
    comFwd = detect_data_hazards_with_forwarding(instructionDetails)
    if comFwd:
        for h in comFwd:
            print(f"  {h.description}")
    else:
        print("  Nenhum conflito load-use detectado.")

    print("\n--- Conflitos de controle ---")
    controle = detect_control_hazards(instructionDetails)
    if controle:
        for h in controle:
            print(f"  {h.description}")
    else:
        print("  Nenhum conflito de controle detectado.")

    # Geracao de arquivos e sobrecusto
    tecnicas = [
        ("dados_sem_forwarding",     "Dados s/ Forwarding",   insert_nops_no_forwarding(instructionDetails)),
        ("dados_com_forwarding",     "Dados c/ Forwarding",   insert_nops_with_forwarding(instructionDetails)),
        ("controle_sem_forwarding",  "Controle s/ Forwarding",insert_nops_control_hazard(instructionDetails)),
        ("controle_com_forwarding",  "Controle c/ Forwarding",insert_nops_control_hazard(instructionDetails)),
        ("integrado_sem_forwarding", "Integrado s/ Forwarding",insert_nops_integrated_no_forwarding(instructionDetails)),
        ("integrado_com_forwarding", "Integrado c/ Forwarding",insert_nops_integrated_with_forwarding(instructionDetails)),
    ]

    print("\n--- Sobrecusto por tecnica ---")
    for nome, label, rows in tecnicas:
        nops = sum(1 for r in rows if r.is_nop)
        pct = nops / n * 100 if n > 0 else 0.0
        arquivo = f"output_{nome}.txt"
        write_rows_to_file(rows, arquivo)
        print(f"  {label}: {nops} NOPs ({pct:.1f}% de sobrecusto) → {arquivo}")

    print()

    ui = InstructionViewer(instructionDetails)
    ui.mainloop()


if __name__ == "__main__":
    main()

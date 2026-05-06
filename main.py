# -*- coding: utf-8 -*-
# Trabalho M1/M2 - Identificação de Instruções RISC-V e Análise de Hazards no Pipeline
# Matéria: Organização de Computadores
# Professor: Thiago Felski
# Grupo: Guilherme Thomy, Ismael Junior, Eduardo Leopoldo

import tkinter as tk
from tkinter import filedialog

from Domain.Entities.InstructionDetails import InstructionDetails
from Domain.Services.HazardAnalyzer import (
    detect_data_hazards_no_forwarding,
    detect_data_hazards_with_forwarding,
    detect_control_hazards,
    detect_control_hazards_with_forwarding,
    insert_nops_no_forwarding,
    insert_nops_with_forwarding,
    insert_nops_control_hazard,
    insert_nops_control_hazard_with_forwarding,
    insert_nops_integrated_no_forwarding,
    insert_nops_integrated_with_forwarding,
    write_rows_to_file,
)
from Presentation.Models.InstructionViewer import InstructionViewer


def readEachLineFromFile(filename: str) -> list[str]:
    # Lê o arquivo linha por linha e converte tudo para hex de 8 dígitos.
    # Suporta arquivos hex (dump do RARS) e arquivos binários de 32 bits.
    lines: list[str] = []
    with open(filename, "r", encoding="utf-8") as file:
        for lineno, line in enumerate(file, start=1):
            stripped = line.strip()
            # Ignora linhas vazias e comentários
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue
            token = stripped.split()[0].lower()
            # Remove o prefixo 0x ou 0b se o arquivo tiver
            if token.startswith("0x"):
                token = token[2:]
            elif token.startswith("0b"):
                token = token[2:]
            try:
                if len(token) == 8 and all(c in "0123456789abcdef" for c in token):
                    lines.append(token)
                else:
                    # Se não é hex de 8 dígitos, trata como binário de 32 bits
                    lines.append(f"{int(token, 2):08x}")
            except ValueError:
                print(f"  [Aviso] Linha {lineno} ignorada (formato invalido): '{stripped}'")
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

    print("\n--- Conflitos de controle (sem forwarding) ---")
    controle_sf = detect_control_hazards(instructionDetails)
    if controle_sf:
        for h in controle_sf:
            print(f"  {h.description}")
    else:
        print("  Nenhum conflito de controle detectado.")

    print("\n--- Conflitos de controle (com forwarding) ---")
    controle_cf = detect_control_hazards_with_forwarding(instructionDetails)
    if controle_cf:
        for h in controle_cf:
            print(f"  {h.description}")
        print("  (Forwarding de dados nao elimina conflitos de controle — resultado identico ao sem forwarding.)")
    else:
        print("  Nenhum conflito de controle detectado.")

    # Geracao de arquivos e sobrecusto
    tecnicas = [
        ("dados_sem_forwarding",     "Dados s/ Forwarding",    insert_nops_no_forwarding(instructionDetails)),
        ("dados_com_forwarding",     "Dados c/ Forwarding",    insert_nops_with_forwarding(instructionDetails)),
        ("controle_sem_forwarding",  "Controle s/ Forwarding", insert_nops_control_hazard(instructionDetails)),
        ("controle_com_forwarding",  "Controle c/ Forwarding", insert_nops_control_hazard_with_forwarding(instructionDetails)),
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

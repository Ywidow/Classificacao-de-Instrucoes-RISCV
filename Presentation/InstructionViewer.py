import tkinter as tk
from tkinter import ttk

from Entities.InstructionDetails import InstructionDetails

class InstructionViewer(tk.Tk):
    def __init__(self, instructions: list[InstructionDetails]):
        super().__init__()
        self.title("Visualizador de Instruções RISC-V")
        self.geometry("1100x700")
        self.configure(bg="#f4f6f8")

        tk.Label(
            self,
            text="Instruções",
            font=("Segoe UI", 18, "bold"),
            bg="#f4f6f8"
        ).pack(pady=10)

        container = tk.Frame(self, bg="#f4f6f8")
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg="#f4f6f8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)

        scrollable_frame = tk.Frame(canvas, bg="#f4f6f8")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        columns = 3

        for i, inst in enumerate(instructions):
            row = i // columns
            col = i % columns

            card = self.create_card(scrollable_frame, inst, i + 1)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        for c in range(columns):
            scrollable_frame.grid_columnconfigure(c, weight=1)

    def create_card(self, parent, inst: InstructionDetails, index: int):
        card = tk.Frame(parent, bg="white", highlightbackground="#ccc", highlightthickness=1)
        card.configure(width=320)
        card.grid_propagate(False)

        header = tk.Label(
            card,
            text=f"Instrução {inst.type.instr_type}",
            font=("Segoe UI", 12, "bold"),
            bg="#e0ecff"
        )
        header.pack(fill="x")

        body = tk.Frame(card, bg="white")
        body.pack(fill="x", padx=10, pady=10)

        self.add_field(body, "Hex:", inst.hexInstruction, 0)
        self.add_field(body, "Bin:", inst.binInstruction, 1)
        self.add_field(body, "OpCode:", str(inst.opCode.opcode), 2)

        row = 4
        tk.Label(
            body,
            text="Propriedades:",
            font=("Segoe UI", 10, "bold"),
            bg="white"
        ).grid(row=row, column=0, sticky="w")

        props_frame = tk.Frame(body, bg="#f9fafb")
        props_frame.grid(row=row, column=1, sticky="w")

        if inst.specificProperties:
            for i, (k, v) in enumerate(inst.specificProperties.items()):
                tk.Label(
                    props_frame,
                    text=f"{k}:",
                    bg="#f9fafb",
                    font=("Segoe UI", 9, "bold")
                ).grid(row=i, column=0, sticky="w")

                tk.Label(
                    props_frame,
                    text=v,
                    bg="#f9fafb",
                    font=("Consolas", 9)
                ).grid(row=i, column=1, sticky="w")
        else:
            tk.Label(
                props_frame,
                text="(vazio)",
                bg="#f9fafb"
            ).grid(row=0, column=0)

        return card

    def add_field(self, parent, label, value, row):
        tk.Label(
            parent,
            text=label,
            font=("Segoe UI", 10, "bold"),
            bg="white"
        ).grid(row=row, column=0, sticky="w", pady=2)

        tk.Label(
            parent,
            text=value,
            font=("Consolas", 10),
            bg="white"
        ).grid(row=row, column=1, sticky="w", pady=2)

import tkinter as tk
from tkinter import ttk

from Domain.Entities.InstructionDetails import InstructionDetails
from Domain.Enums.InstructionType import InstructionType
from Domain.Services.HazardAnalyzer import (
    InstructionRow,
    BRANCH_TYPES,
    create_demo_sequence,
    insert_nops_no_forwarding,
    insert_nops_with_forwarding,
    insert_nops_control_hazard,
    insert_nops_control_hazard_with_forwarding,
    insert_nops_integrated_no_forwarding,
    insert_nops_integrated_with_forwarding,
    detect_data_hazards_no_forwarding,
    detect_data_hazards_with_forwarding,
    detect_control_hazards,
    detect_control_hazards_with_forwarding,
)

_TAB_INFO = [
    ("Original",            None),
    ("Dados s/ Fwd",        insert_nops_no_forwarding),
    ("Dados c/ Fwd",        insert_nops_with_forwarding),
    ("Controle s/ Fwd",     insert_nops_control_hazard),
    ("Controle c/ Fwd",     insert_nops_control_hazard_with_forwarding),
    ("Integrado s/ Fwd",    insert_nops_integrated_no_forwarding),
    ("Integrado c/ Fwd",    insert_nops_integrated_with_forwarding),
]

_DEMO_COMMENTS = {
    0: "add x1, x2, x3  → escreve x1",
    1: "add x4, x1, x5  → lê x1 (escrito na instr. 0) ← hazard RAW",
    2: "add x6, x4, x7  → lê x4 (escrito na instr. 1) ← hazard RAW",
    3: "lw  x8, 0(x6)   → lê x6 (escrito na instr. 2) ← hazard RAW + LOAD",
    4: "add x9, x8, x1  → lê x8 (carregado na instr. 3) ← hazard load-use",
    5: "beq x1, x4, +8  → desvio para instr. 7 ← hazard de controle",
    6: "add x10, x2, x3 → pode ser descartada se desvio for tomado",
    7: "add x11, x1, x4 → alvo do desvio",
}

_DESCRIPTIONS = {
    "Original": "Sequência original, sem nenhuma modificação.",
    "Dados s/ Fwd": (
        "Conflito de dados — sem forwarding.\n"
        "Sem forwarding, o valor escrito num registrador só fica disponível depois do WB (5º estágio). "
        "Por isso, a instrução leitora precisa esperar: dist=1 → 3 NOPs | dist=2 → 2 NOPs | dist=3 → 1 NOP."
    ),
    "Dados c/ Fwd": (
        "Conflito de dados — com forwarding (EX→EX e MEM→EX).\n"
        "Com forwarding, o resultado é repassado direto entre os estágios e a maioria dos conflitos desaparece. "
        "O único caso que ainda precisa de NOP é o load-use: o lw só tem o dado no MEM, "
        "que chega 1 ciclo depois do que o próximo EX precisa — então 1 NOP é inevitável."
    ),
    "Controle s/ Fwd": (
        "Conflito de controle — sem forwarding de dados.\n"
        "O endereço de destino do branch só é conhecido no EX (ciclo 3). Enquanto isso, "
        "2 instruções já entraram no pipeline e precisam ser descartadas. "
        "A solução é inserir 2 NOPs depois de cada branch ou jal."
    ),
    "Controle c/ Fwd": (
        "Conflito de controle — com forwarding de dados.\n"
        "Forwarding não resolve conflito de controle: o problema não é um registrador atrasado, "
        "é não saber para onde o programa vai depois do desvio. "
        "A solução é a mesma: 2 NOPs após cada branch ou jal."
    ),
    "Integrado s/ Fwd": (
        "Solução integrada — sem forwarding.\n"
        "Resolve os dois tipos de conflito juntos numa única passagem: "
        "até 3 NOPs para conflitos de dados e 2 NOPs após cada desvio para conflitos de controle. "
        "Os endereços dos desvios são recalculados automaticamente."
    ),
    "Integrado c/ Fwd": (
        "Solução integrada — com forwarding.\n"
        "Com forwarding, só o load-use ainda precisa de NOP (1 NOP). "
        "Os conflitos de controle continuam precisando de 2 NOPs após cada desvio. "
        "Os endereços dos desvios são recalculados automaticamente."
    ),
}


class PipelineViewer(tk.Toplevel):
    def __init__(self, parent, instructions: list[InstructionDetails], base_addr: int = 0):
        super().__init__(parent)
        self.title("Análise de Hazards – Pipeline RISC-V (M2)")
        self.geometry("1100x680")
        self.configure(bg="#f4f6f8")

        tk.Label(
            self,
            text="Análise de Hazards no Pipeline RISC-V",
            font=("Segoe UI", 15, "bold"),
            bg="#f4f6f8",
        ).pack(pady=(10, 4))

        main_notebook = ttk.Notebook(self)
        main_notebook.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        # ── Aba de detecção ──────────────────────────────────────────────────
        detect_frame = tk.Frame(main_notebook, bg="#f4f6f8")
        main_notebook.add(detect_frame, text="Deteccao de Hazards")
        self._build_detection_tab(detect_frame, instructions)

        # ── Aba de pipeline ──────────────────────────────────────────────────
        pipeline_frame = tk.Frame(main_notebook, bg="#f4f6f8")
        main_notebook.add(pipeline_frame, text="Correcao com NOPs")

        notebook = ttk.Notebook(pipeline_frame)
        notebook.pack(fill="both", expand=True)

        # ── Tabs for the loaded instruction file ──────────────────────────────
        orig_rows = [InstructionRow(inst, False, i) for i, inst in enumerate(instructions)]
        for title, fn in _TAB_INFO:
            rows = orig_rows if fn is None else fn(instructions, base_addr)
            self._add_tab(notebook, title, rows, len(instructions), base_addr)

        # ── Demo tabs with a sequence that has real hazards ───────────────────
        demo = create_demo_sequence()
        demo_orig = [InstructionRow(inst, False, i) for i, inst in enumerate(demo)]

        sep = ttk.Frame(notebook)
        notebook.add(sep, text="──── DEMO ────", state="disabled")

        self._add_tab(notebook, "Demo: Original",
                      demo_orig, len(demo), base_addr, _DEMO_COMMENTS)
        self._add_tab(notebook, "Demo: Sem Forwarding",
                      insert_nops_no_forwarding(demo, base_addr), len(demo), base_addr, _DEMO_COMMENTS)
        self._add_tab(notebook, "Demo: Com Forwarding",
                      insert_nops_with_forwarding(demo, base_addr), len(demo), base_addr, _DEMO_COMMENTS)
        self._add_tab(notebook, "Demo: Controle",
                      insert_nops_control_hazard(demo, base_addr), len(demo), base_addr, _DEMO_COMMENTS)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _build_detection_tab(self, parent: tk.Frame, instructions: list[InstructionDetails]):
        """Aba que exibe os hazards detectados (itens 1a, 1b, 2a, 2b da atividade)."""
        sections = [
            (
                "1a. Conflitos de Dados — Sem Forwarding",
                "#fff3cd",
                detect_data_hazards_no_forwarding(instructions),
                "Hazard RAW detectado: uma instrução lê um registrador que ainda não foi escrito (WB não concluído).\n"
                "dist=1 → 3 NOPs necessários  |  dist=2 → 2 NOPs  |  dist=3 → 1 NOP",
            ),
            (
                "1b. Conflitos de Dados — Com Forwarding",
                "#d4edda",
                detect_data_hazards_with_forwarding(instructions),
                "Com forwarding (EX→EX e MEM→EX), apenas o hazard load-use continua exigindo NOP.\n"
                "Ocorre quando um lw é seguido diretamente por uma instrução que usa o registrador carregado.",
            ),
            (
                "2a. Conflitos de Controle — Sem Forwarding",
                "#cce5ff",
                detect_control_hazards(instructions),
                "Toda instrução de desvio (beq, bne...) ou salto (jal) causa conflito de controle.\n"
                "O endereço de destino só é conhecido no final do EX, e 2 instruções já entraram no pipeline — por isso 2 NOPs.",
            ),
            (
                "2b. Conflitos de Controle — Com Forwarding",
                "#e2d9f3",
                detect_control_hazards_with_forwarding(instructions),
                "Forwarding de dados NÃO elimina conflitos de controle — o problema é o atraso para saber o endereço do desvio.\n"
                "A detecção é idêntica ao caso sem forwarding: 2 NOPs em todo desvio/salto.",
            ),
        ]

        canvas = tk.Canvas(parent, bg="#f4f6f8", highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        inner = tk.Frame(canvas, bg="#f4f6f8")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for title, color, reports, desc in sections:
            sec = tk.LabelFrame(inner, text=title, font=("Segoe UI", 10, "bold"),
                                bg=color, padx=8, pady=6)
            sec.pack(fill="x", padx=10, pady=6)
            tk.Label(sec, text=desc, font=("Segoe UI", 8), bg=color,
                     justify="left", anchor="w").pack(fill="x")
            if reports:
                for h in reports:
                    tk.Label(sec, text=h.description, font=("Consolas", 9),
                             bg=color, anchor="w", justify="left").pack(fill="x", pady=1)
                tk.Label(sec, text=f"Total: {len(reports)} conflito(s) detectado(s).",
                         font=("Segoe UI", 9, "bold"), bg=color).pack(anchor="w", pady=(4, 0))
            else:
                tk.Label(sec, text="  Nenhum conflito detectado.",
                         font=("Segoe UI", 9, "italic"), bg=color).pack(anchor="w")

    def _add_tab(
        self,
        notebook: ttk.Notebook,
        title: str,
        rows: list[InstructionRow],
        n_orig: int,
        base_addr: int,
        orig_comments: dict[int, str] | None = None,
    ):
        outer = tk.Frame(notebook, bg="#f4f6f8")
        notebook.add(outer, text=title)

        # Description banner
        desc = _DESCRIPTIONS.get(title, "")
        tk.Label(
            outer, text=desc, font=("Segoe UI", 9), bg="#dbe9ff",
            justify="left", anchor="w", wraplength=1060, padx=8, pady=4,
        ).pack(fill="x", pady=(4, 0))

        # Table
        cols = ("Endereço", "Hex", "Instrução", "Observação")
        frame = tk.Frame(outer, bg="#f4f6f8")
        frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(frame, columns=cols, show="headings")
        tree.heading("Endereço", text="Endereço")
        tree.heading("Hex",      text="Hex")
        tree.heading("Instrução", text="Instrução")
        tree.heading("Observação", text="Observação / Hazard")

        tree.column("Endereço",   width=100, anchor="center", stretch=False)
        tree.column("Hex",        width=120, anchor="center", stretch=False)
        tree.column("Instrução",  width=160, anchor="center", stretch=False)
        tree.column("Observação", width=680, anchor="w")

        tree.tag_configure("nop",    background="#FFF3CD", foreground="#7a5000")
        tree.tag_configure("branch", background="#D4EDDA", foreground="#155724")
        tree.tag_configure("normal", background="white")

        vsb = ttk.Scrollbar(frame, orient="vertical",   command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        nop_count = 0
        for new_idx, row in enumerate(rows):
            addr = f"0x{base_addr + new_idx * 4:04X}"
            hex_val = row.inst.hexInstruction.upper()

            if row.is_nop:
                instr = "NOP  (addi x0, x0, 0)"
                note  = "← inserido para resolver hazard"
                tag   = "nop"
                nop_count += 1
            else:
                instr = row.inst.type.instr_type
                parts = []
                if orig_comments and row.original_idx in orig_comments:
                    parts.append(orig_comments[row.original_idx])
                if row.note:
                    parts.append(row.note)
                note = "  |  ".join(parts)
                tag  = "branch" if row.note else "normal"

            tree.insert("", "end", values=(addr, hex_val, instr, note), tags=(tag,))

        # Stats bar
        stat = (
            f"Instruções originais: {n_orig}  |  "
            f"NOPs inseridos: {nop_count}  |  "
            f"Total no pipeline: {len(rows)}"
        )
        tk.Label(
            outer, text=stat, font=("Segoe UI", 9, "bold"),
            bg="#e8eaf6", anchor="w", padx=8, pady=3,
        ).pack(fill="x", side="bottom")

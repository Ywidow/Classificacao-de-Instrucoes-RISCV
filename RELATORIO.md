# Relatório Técnico — Classificação de Instruções RISC-V e Análise de Hazards no Pipeline

**Matéria:** Organização de Computadores
**Professor:** Thiago Felski
**Grupo:** Guilherme Thomy, Ismael Junior, Eduardo Leopoldo

---

## Sumário

1. [Contexto: como uma instrução RISC-V é codificada](#1-contexto-como-uma-instrução-risc-v-é-codificada)
2. [Estrutura do projeto](#2-estrutura-do-projeto)
3. [Domain/Enums/OpCode.py](#3-domainenumsopcodepy)
4. [Domain/Enums/InstructionType.py](#4-domainenumsinstructiontypepy)
5. [Domain/Entities/InstructionDetails.py](#5-domainentitiesinstructiondetailspy)
6. [Domain/Builders/TypeBuilder.py](#6-domainbuilderstypebuilderpyy)
7. [Domain/Builders/SpecificPropertiesBuilder.py](#7-domainbuildersspecificpropertiesbuilderpyy)
8. [Domain/Services/HazardAnalyzer.py](#8-domainserviceshazardanalyzerpy)
9. [Presentation/Models/InstructionViewer.py](#9-presentationmodelsinstructionviewerpy)
10. [Presentation/Models/PipelineViewer.py](#10-presentationmodelspipelineviewerpy)
11. [main.py](#11-mainpy)

---

## 1. Contexto: como uma instrução RISC-V é codificada

Antes de entender o código, é essencial entender como o hardware RISC-V representa uma instrução na memória.

Toda instrução RISC-V tem **exatamente 32 bits** (4 bytes). Esses bits são divididos em campos com significados fixos. Os principais campos são:

```
 31      25 24    20 19    15 14  12 11     7 6       0
 ┌────────┬────────┬────────┬──────┬────────┬─────────┐
 │ funct7 │  rs2   │  rs1   │funct3│   rd   │ opcode  │
 └────────┴────────┴────────┴──────┴────────┴─────────┘
   7 bits   5 bits   5 bits  3 bits  5 bits   7 bits
```

### O que é cada campo?

| Campo    | Bits     | O que significa                                                                                                                                  |
|----------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `opcode` | [6:0]    | Os 7 bits menos significativos. Identificam a **família** da instrução (tipo R, I, S, B, U ou J). É o primeiro filtro para saber o que fazer.   |
| `rd`     | [11:7]   | **Destination Register** — o registrador de **destino**, onde o resultado da instrução vai ser escrito. Ex: `add x1, x2, x3` → `rd = x1`.      |
| `funct3` | [14:12]  | 3 bits que **refinam** o opcode. Como vários opcodes cobrem várias instruções (ex.: `0b0110011` cobre `add`, `sub`, `and`, `or`...), o funct3 diferencia cada uma. |
| `rs1`    | [19:15]  | **Register Source 1** — primeiro registrador de **leitura**. A instrução vai **ler** o valor desse registrador. Ex: em `add x1, x2, x3` → `rs1 = x2`. |
| `rs2`    | [24:20]  | **Register Source 2** — segundo registrador de **leitura** (quando existir). Ex: em `add x1, x2, x3` → `rs2 = x3`.                            |
| `funct7` | [31:25]  | 7 bits extras para diferenciar ainda mais. Usado principalmente para separar `add` de `sub` e `srl` de `sra` (o funct3 é igual nesses pares).  |
| `imm`    | vários   | **Immediate** — valor imediato embutido na instrução. Não vem de registrador, é um número literal. Os bits ficam **espalhados** na instrução dependendo do formato. |

### Por que os números dos campos parecem "invertidos" no código?

O RISC-V numera os bits do **menos significativo (bit 0) para o mais significativo (bit 31)**. Já em Python, quando convertemos para string binária com `format(valor, '032b')`, o bit mais significativo fica na **posição 0 da string** (à esquerda). Por isso:

- `binInstruction[-7:]` → pega os últimos 7 caracteres da string → que são os bits [6:0] → o **opcode**.
- `binInstruction[20:25]` → posições 20 a 24 da string → que correspondem aos bits [11:7] → o **rd**.
- `binInstruction[12:17]` → posições 12 a 16 da string → que correspondem aos bits [19:15] → o **rs1**.
- `binInstruction[7:12]`  → posições 7 a 11 da string → que correspondem aos bits [24:20] → o **rs2**.
- `binInstruction[17:20]` → posições 17 a 19 da string → que correspondem aos bits [14:12] → o **funct3**.
- `binInstruction[1:8]`   → posições 1 a 7 da string  → que correspondem aos bits [30:25] (parte do funct7).

---

## 2. Estrutura do projeto

```
.
├── main.py                                  # Ponto de entrada
├── Domain/
│   ├── Enums/
│   │   ├── OpCode.py                        # Enum com todos os opcodes
│   │   └── InstructionType.py               # Enum com todos os tipos de instrução
│   ├── Entities/
│   │   └── InstructionDetails.py            # Entidade que representa uma instrução decodificada
│   ├── Builders/
│   │   ├── TypeBuilder.py                   # Identifica qual instrução é (add, lw, beq...)
│   │   └── SpecificPropertiesBuilder.py     # Extrai os campos (rd, rs1, rs2, imm...) da instrução
│   └── Services/
│       └── HazardAnalyzer.py                # Detecção e resolução de hazards no pipeline
└── Presentation/
    └── Models/
        ├── InstructionViewer.py             # Janela principal (cards das instruções)
        └── PipelineViewer.py                # Janela de análise do pipeline com NOPs
```

O projeto segue uma arquitetura em camadas:
- **Domain** contém toda a lógica de negócio (decodificação e análise).
- **Presentation** contém apenas a interface gráfica.
- As camadas de Presentation conhecem o Domain, mas o Domain não conhece a Presentation.

---

## 3. `Domain/Enums/OpCode.py`

```python
class OpCode(Enum):
    U0110111 = ("0110111")
    R0110011 = ("0110011")
    ...
```

### Por que existe?

No RISC-V, o opcode é apenas um número de 7 bits. Usar strings como `"0110011"` espalhadas pelo código seria frágil e ilegível. O `Enum` transforma esses valores brutos em **nomes com significado**.

O nome de cada membro segue o padrão `<Tipo><Opcode>`. Exemplos:
- `R0110011` → instrução do tipo R com opcode `0110011` (add, sub, and, or...)
- `I0000011` → instrução do tipo I com opcode `0000011` (loads: lb, lh, lw...)
- `B1100011` → instrução do tipo B com opcode `1100011` (branches: beq, bne...)

### Por que o mesmo opcode pode cobrir várias instruções?

O RISC-V economiza opcodes agrupando instruções parecidas. O opcode diz a família; o funct3 diz a instrução específica dentro da família. Por isso há apenas 11 opcodes mas dezenas de instruções.

---

## 4. `Domain/Enums/InstructionType.py`

```python
class InstructionType(Enum):
    RADD  = ("0110011", "R add")
    RSUB  = ("0110011", "R sub")
    BBEQ  = ("1100011", "B beq")
    ILW   = ("0000011", "I lw")
    ...
```

### Por que existe?

Enquanto o `OpCode` identifica a **família**, o `InstructionType` identifica a **instrução específica**. Cada membro carrega:
1. O opcode (string de 7 bits) — campo `opcode`.
2. O nome legível no formato `"<Tipo> <nome>"` — campo `instr_type`. Esse campo é exibido na interface.

Os prefixos dos nomes indicam o formato de codificação:
- `R` → formato Register (usa rs1, rs2, rd, funct3, funct7)
- `I` → formato Immediate (usa rs1, rd, imm de 12 bits)
- `S` → formato Store (usa rs1, rs2, imm espalhado)
- `B` → formato Branch (usa rs1, rs2, imm espalhado para offset de desvio)
- `U` → formato Upper (usa rd e imm de 20 bits)
- `J` → formato Jump (usa rd e imm de 20 bits espalhado)

---

## 5. `Domain/Entities/InstructionDetails.py`

Esta é a **entidade central** do sistema. Ela representa uma instrução completamente decodificada.

### `__init__(self, hexInstruction: str)`

Recebe a instrução como string hexadecimal de 8 dígitos (ex.: `"00628233"`) e dispara toda a cadeia de decodificação em sequência:

```
hex → binário → opcode → tipo → propriedades específicas
```

Cada passo depende do anterior, por isso é feito em ordem.

### `setBinInstruction(hexInstruction: str) -> str`

Converte os 8 dígitos hex em uma string de 32 caracteres de 0s e 1s.

```python
format(int("00628233", 16), "032b")
# → "00000000011000101000001000110011"
```

**Por que armazenar como string e não como inteiro?** Porque o Python não tem tipo de "inteiro de 32 bits com acesso a bits por faixa". A string permite fazer slices diretamente (`binInstruction[12:17]`) sem operações bit a bit manuais.

### `setOpCode(self) -> OpCode`

Extrai os 7 últimos caracteres da string binária — que correspondem aos bits [6:0] — e converte para o enum `OpCode`.

```python
self.binInstruction[-7:]  # pega os 7 bits do opcode
```

**Por que [-7:] e não [25:32]?** São equivalentes. `[-7:]` é mais idiomático em Python para "os últimos 7 caracteres".

### `print(self)` e `printSpecificProperties(self) -> str`

Métodos de debug que formatam e imprimem todos os campos da instrução no terminal. Úteis durante o desenvolvimento.

---

## 6. `Domain/Builders/TypeBuilder.py`

### `defineTypeForInstruction(opCode, binInstruction) -> InstructionType`

Dado o opcode (que identifica a família) e a instrução binária completa, determina **qual instrução específica** é.

Usa um `match` no opcode. Para opcodes que mapeiam para uma única instrução (como `LUI` e `AUIPC`), retorna diretamente. Para os que cobrem várias, delega para uma função auxiliar que lê o **funct3**.

### `handleTypeWhenOpCodeIsR0110011(binInstruction)` e similares

Cada uma dessas funções lida com um opcode que agrupa várias instruções. Todas fazem a mesma coisa:

1. Extrai o funct3: `binInstruction[17:20]` (bits [14:12]).
2. Usa um `match` no funct3 para identificar a instrução.
3. Quando funct3 é ambíguo (ex.: `000` serve para `add` e `sub`), lê também o **funct7** (`binInstruction[1:8]`, bits [30:24]) para decidir.

**Exemplo concreto — distinguir ADD de SUB:**
- Ambos têm funct3 = `000`.
- `ADD` tem funct7 = `0000000`.
- `SUB` tem funct7 = `0100000` (bit 30 = 1).
- O código verifica `if '1' not in funct7` → se não tem nenhum bit 1, é `ADD`; senão é `SUB`.

**Exemplo — distinguir SRLI de SRAI (shift lógico vs aritmético):**
- Ambos têm funct3 = `101`.
- `SRLI` tem funct7 = `0000000` (shift lógico, preenche com 0).
- `SRAI` tem funct7 = `0100000` (shift aritmético, preserva o bit de sinal).
- Mesma lógica do ADD/SUB.

**Por que o funct7 para ECALL/EBREAK usa `binInstruction[1:13]` e não `[1:8]`?**
Porque `ECALL` e `EBREAK` são instruções do sistema que não têm rs1, rs2 nem rd "de verdade". O campo que seria o "imm" de 12 bits funciona como discriminador. Para `ECALL` todos os bits são 0; para `EBREAK` o bit 20 (posição 11 da string, parte do "funct12") é 1. O slice `[1:13]` captura esses 12 bits.

---

## 7. `Domain/Builders/SpecificPropertiesBuilder.py`

Esta classe é responsável por extrair os **campos individuais** de cada instrução (rd, rs1, rs2, imm, shamt, csr...) e armazená-los como dicionário de strings legíveis.

### `buildSpecificProperties(self) -> dict[str, str]`

Função principal. Decide qual método de extração usar baseado no tipo/opcode da instrução. A ordem dos `if` importa — tipos mais específicos são verificados antes dos genéricos.

### `setRd(self)`, `setRs1(self)`, `setRs2(self)`

Extraem os campos de registrador da instrução binária. Cada um lê uma faixa específica de bits e converte para inteiro decimal (que é o número do registrador).

```python
def setRd(self):
    # bits [11:7] → posições [20:25] na string (MSB à esquerda)
    self.specificProperties['Rd'] = f'{self.binInstruction[20:25]} ({int(self.binInstruction[20:25], 2)})'
```

O resultado é armazenado como `"00001 (1)"` — mostrando os bits e o número do registrador. Isso facilita a conferência visual.

**Por que x0 nunca causa hazard?** O registrador x0 no RISC-V é **hardwired zero** — é fisicamente um fio ligado ao terra. Escrever nele não faz nada, e ler dele sempre dá 0. Por isso, o `HazardAnalyzer` ignora x0 ao verificar conflitos.

### `setSpecificPropertiesForBranch(self)`

As instruções de branch têm o imediato **embaralhado** na instrução por uma razão histórica: o bit de sinal (bit 12 do imediato) ficou em um lugar "ruim" na especificação original, e os projetistas do RISC-V reorganizaram os bits para minimizar multiplexadores no hardware.

A remontagem é:
```python
imm1 = f'{self.binInstruction[19]}{self.binInstruction[21:27]}'  # bits [11] e [10:5]
imm2 = f'{self.binInstruction[27:31]}{self.binInstruction[20]}'  # bits [4:1] e [12]
```

O offset completo de 13 bits (sempre múltiplo de 2, pois instrução RISC-V ocupa 4 bytes e o bit 0 é sempre 0) é: `imm[12|11|10:5|4:1|0]`.

### `setSpecificPropertiesForJump(self)`

O formato J (usado pelo `JAL`) também tem o imediato embaralhado, com uma reorganização diferente do B:
```python
imm = (f'{self.binInstruction[11]}'    # bit [20]
       f'{self.binInstruction[21:32]}' # bits [10:1]
       f'{self.binInstruction[20]}'    # bit [11]
       f'{self.binInstruction[12:20]}')# bits [19:12]
```

O resultado é um offset de 21 bits com alcance de ±1 MB.

### `setSpecificPropertiesForImmediatesWithShamt(self)`

Para instruções de shift imediato (`slli`, `srli`, `srai`), o campo "rs2" não é um registrador — é o **shamt** (shift amount), a quantidade de posições a deslocar (0 a 31). Por isso tem apenas 5 bits e é extraído da mesma faixa que seria rs2.

### `setCsr(self)` e `setSpecificPropertiesForImmediateWithCsrAndZimm(self)`

As instruções CSR (Control and Status Register) acessam registradores especiais do processador (controle de interrupções, contadores de ciclo, etc.). O campo `csr` é um endereço de 12 bits que identifica qual registrador especial acessar. O `zimm` (zero-extended immediate) é um valor de 5 bits usado pelas versões imediatas das instruções CSR.

---

## 8. `Domain/Services/HazardAnalyzer.py`

Este é o módulo mais complexo do projeto. Implementa toda a lógica de detecção e resolução de **hazards no pipeline**.

### Contexto: o que é um hazard?

Um pipeline de 5 estágios (IF → ID → EX → MEM → WB) executa várias instruções simultaneamente, cada uma em um estágio diferente. O problema é que às vezes uma instrução **precisa de um dado que ainda não está pronto** porque a instrução anterior ainda não terminou de calculá-lo. Isso é um **hazard**.

### Constantes e conjuntos

```python
NOP_HEX = '00000013'  # addi x0, x0, 0
```

O NOP ("No Operation") padrão do RISC-V é `addi x0, x0, 0` — soma 0 ao registrador zero e joga o resultado no zero. Não faz absolutamente nada, mas ocupa um ciclo de clock, que é exatamente o que precisamos para "esperar".

```python
LOAD_TYPES = frozenset({ILB, ILH, ILW, ILBU, ILHU})
BRANCH_TYPES = frozenset({BBEQ, BBNE, BBLT, BBGE, BBLTU, BBGEU})
WRITES_RD_OPCODES = frozenset({...})
READS_RS1_OPCODES = frozenset({...})
READS_RS2_OPCODES = frozenset({...})
```

Conjuntos imutáveis (`frozenset`) para verificações rápidas (`inst.type in LOAD_TYPES`). São mais eficientes do que múltiplos `if/elif`.

- `WRITES_RD_OPCODES`: instruções que **escrevem** um resultado em rd — só essas podem causar RAW hazard.
- `READS_RS1/RS2_OPCODES`: instruções que **leem** rs1 ou rs2 — só essas podem ser vítimas de um RAW hazard.
- Instruções de store (S-type) leem rs1 e rs2 mas **não escrevem rd** — elas nunca causam RAW hazard na frente, mas podem ser vítimas.

### `_get_rd(inst)`, `_get_rs1(inst)`, `_get_rs2(inst)`

Funções auxiliares que extraem o número do registrador (inteiro de 0 a 31) de uma instrução, ou retornam `None` se a instrução não usa aquele campo.

`_get_rd` trata o caso especial de `rd == 0` (x0): como x0 nunca muda, escrever nele não pode causar hazard e retorna `None`.

### `_get_branch_offset(inst) -> int`

Extrai o **offset de desvio** de instruções branch e JAL. O offset indica em quantos bytes o PC deve avançar ou recuar se o desvio for tomado.

A lógica remonta os bits embaralhados do imediato (mesma lógica do `SpecificPropertiesBuilder`) e aplica extensão de sinal: se o bit mais significativo for 1, o offset é negativo (desvio para trás no código).

```python
if b[0] == '1':   # bit de sinal
    val -= (1 << 13)  # converte de complemento de 2 para inteiro Python
```

**Por que o offset é sempre múltiplo de 4?** Instruções RISC-V ocupam exatamente 4 bytes. Nunca faz sentido saltar para o meio de uma instrução, então o bit 0 do offset é sempre 0 (implícito, não armazenado).

### `_encode_with_new_offset(inst, new_offset) -> InstructionDetails`

Quando NOPs são inseridos entre instruções, os desvios ficam errados: uma instrução que pulava 8 bytes para frente talvez precise pular 20 bytes agora (porque foram inseridos 3 NOPs de 4 bytes cada no caminho).

Esta função **recodifica** a instrução de desvio com o novo offset, remontando os bits na ordem correta do formato RISC-V e recriando a instrução completa como um novo `InstructionDetails`.

### `_run(instructions, compute_data_nops, control_nops, base_addr) -> list[InstructionRow]`

**Função central de todo o sistema.** Processa a lista de instruções e produz a sequência final com NOPs inseridos.

**Primeira passagem — inserção de NOPs:**

Usa dois vetores de controle:
- `reg_avail[32]`: para cada registrador, em qual posição da sequência seu valor estará pronto (sem forwarding).
- `reg_load_avail[32]`: idem, mas só para loads (com forwarding).

Para cada instrução:
1. Pergunta `compute_data_nops(...)` quantos NOPs de dados são necessários antes dela.
2. Insere esses NOPs.
3. Registra a posição da instrução no mapeamento `original_to_new` (índice original → índice novo).
4. Atualiza `reg_avail[rd]` com a posição em que o rd estará disponível.

**Por que `reg_avail[rd] = len(raw) + 3`?**

No pipeline de 5 estágios sem forwarding:
- Uma instrução escreve em rd no estágio **WB** (5º).
- Se ela está na posição `p`, ela começa WB no ciclo `p + 4`.
- Uma instrução leitora na posição `p + 1` leria rd no estágio **ID** (ciclo `p + 2`), antes do WB.
- A leitora precisa esperar até a posição `p + 4` para ler com segurança.
- Isso equivale a dizer que `reg_avail[rd] = p + 3` (3 ciclos após a escrita).

**Segunda passagem — correção dos offsets:**

Agora que `original_to_new` está completo, percorre todas as instruções de desvio e recalcula os offsets usando `_encode_with_new_offset`.

Para alvos **dentro** do bloco: usa o mapeamento de posições.
Para alvos **fora** do bloco (endereço absoluto): recalcula com base no `base_addr`.

### `insert_nops_no_forwarding(instructions, base_addr)`

Sem forwarding, qualquer instrução que lê rs1 ou rs2 precisa esperar até que a instrução escritora tenha completado o WB. A função `compute` interna calcula quantos NOPs são necessários comparando a posição atual com `reg_avail[rs]`:

```
NOPs necessários = max(0, reg_avail[rs] - posição_atual)
```

Chama `_run` com `control_nops=0` (sem NOPs de controle) e `compute_data_nops=compute`.

### `insert_nops_with_forwarding(instructions, base_addr)`

Com **forwarding** (ou "data hazard bypassing"), o hardware tem caminhos extras que levam o resultado de um estágio diretamente para o início de outro, sem precisar esperar o WB.

- Forwarding **EX → EX**: o resultado do EX de uma instrução vai direto para o EX da próxima. Elimina RAW para instruções aritméticas/lógicas consecutivas.
- Forwarding **MEM → EX**: o resultado do MEM vai para o EX da instrução seguinte. Elimina RAW para aritmética após aritmética com 1 instrução de distância.

O único caso que forwarding **não resolve** é o **load-use hazard**: uma instrução `lw` só tem o dado no final do estágio MEM (estágio 4), mas a próxima instrução precisa disso no início do EX (estágio 3). O dado chega 1 ciclo tarde. Por isso, usa `reg_load_avail` em vez de `reg_avail`.

### `insert_nops_control_hazard(instructions, base_addr)`

Conflito de controle acontece porque o pipeline busca (IF) instruções de forma especulativa antes de saber se um branch vai ser tomado ou não. O endereço de destino só é calculado no EX (3º estágio), quando 2 instruções já foram buscadas.

A solução simples é inserir **2 NOPs** após cada branch e JAL. Usa `compute_data_nops = lambda *_: 0` (ignora dados) e `control_nops = 2`.

### `insert_nops_control_hazard_with_forwarding(instructions, base_addr)`

Identica à anterior. Forwarding de dados **não ajuda** em conflitos de controle: o problema não é um registrador atrasado, é não saber para onde pular. A latência do cálculo do endereço de desvio é a mesma.

### `insert_nops_integrated_no_forwarding` e `insert_nops_integrated_with_forwarding`

Combinam ambas as estratégias em uma única passagem: NOPs de dados (calculados por `compute`) e NOPs de controle (passados via `control_nops=2`) ao mesmo tempo. O `_run` os insere na ordem correta e corrige os offsets de uma vez.

### `detect_data_hazards_no_forwarding(instructions)`

Percorre todas as instruções. Para cada uma, olha as 3 instruções anteriores (distâncias 1, 2 e 3) em busca de escritas em rd que conflitem com rs1 ou rs2 da instrução atual.

A fórmula de NOPs necessários: `NOPs = 4 - distância`:
- dist=1 (imediatamente anterior) → 3 NOPs
- dist=2 (duas atrás) → 2 NOPs
- dist=3 (três atrás) → 1 NOP
- dist≥4 → 0 NOPs (WB já completou)

### `detect_data_hazards_with_forwarding(instructions)`

Com forwarding, só verifica o caso específico de **load-use**: instrução anterior é um load (`lw`, `lb`...) e a instrução atual lê o mesmo registrador que o load escreveu. Distância sempre 1, sempre 1 NOP.

### `detect_control_hazards(instructions)` e `detect_control_hazards_with_forwarding(instructions)`

Percorre as instruções e reporta cada branch e JAL encontrado. Sempre 2 NOPs.

A versão `with_forwarding` simplesmente chama a sem forwarding e retorna o mesmo resultado, documentando explicitamente que forwarding não muda nada aqui.

### `write_rows_to_file(rows, filename)`

Salva a sequência de instruções (com NOPs) em um arquivo `.txt`, uma instrução por linha em hexadecimal minúsculo. O formato é compatível com o dump do simulador RARS, permitindo reimportar.

### Funções de codificação manual: `_encode_r`, `_encode_lw`, `_encode_beq`

Funções usadas exclusivamente para criar a sequência Demo. Montam instruções RISC-V "na mão" a partir dos parâmetros (registradores, imediatos), posicionando cada campo nos bits corretos conforme a especificação.

Por exemplo, `_encode_r` para uma instrução tipo R:
```
bits 31:25 = funct7
bits 24:20 = rs2
bits 19:15 = rs1
bits 14:12 = funct3
bits 11:7  = rd
bits 6:0   = opcode (0b0110011)
```

### `create_demo_sequence() -> list[InstructionDetails]`

Cria manualmente uma sequência de 8 instruções que contém **todos os tipos de hazard** para fins didáticos:
- RAW de dados (add → add imediato)
- Load-use hazard (lw → add)
- Hazard de controle (beq)

---

## 9. `Presentation/Models/InstructionViewer.py`

### `InstructionViewer(instructions)`

Janela principal da interface gráfica. Exibe as instruções decodificadas em **cards** organizados em grade (3 por linha), com scroll vertical.

Cada card mostra:
- Representação hexadecimal da instrução.
- Representação binária de 32 bits.
- OpCode.
- Propriedades específicas (rd, rs1, rs2, imm...).

O botão "Análise de Hazards" abre o `PipelineViewer`.

### `create_card(parent, inst, index)`

Cria um widget de card para uma instrução. Usa `tk.Frame` como container branco com borda, um header azul claro com o nome da instrução, e campos organizados em grid.

### `add_field(parent, label, value, row)`

Helper que cria um par label/valor na linha `row` do grid do card. Evita repetição de código para cada campo.

### `_open_pipeline_viewer(self)`

Callback do botão que instancia o `PipelineViewer`, passando as instruções carregadas. O import é feito **dentro do método** (import tardio) para evitar importação circular entre as classes de Presentation.

---

## 10. `Presentation/Models/PipelineViewer.py`

### `PipelineViewer(parent, instructions, base_addr)`

Janela filha (`Toplevel`) com dois painéis principais em abas:
1. **Detecção de Hazards** — lista os hazards encontrados por categoria.
2. **Correção com NOPs** — mostra a sequência de instruções com NOPs inseridos, uma aba por técnica.

### `_build_detection_tab(parent, instructions)`

Constrói a aba de detecção. Chama as quatro funções de detecção do `HazardAnalyzer` e exibe cada conjunto de resultados em uma seção colorida (`LabelFrame`).

As cores ajudam na leitura:
- Amarelo: dados sem forwarding.
- Verde: dados com forwarding.
- Azul: controle sem forwarding.
- Roxo: controle com forwarding.

### `_add_tab(notebook, title, rows, n_orig, base_addr, orig_comments)`

Cria uma aba do notebook com uma tabela (`ttk.Treeview`) mostrando a sequência de instruções:

| Coluna      | O que mostra                                                      |
|-------------|-------------------------------------------------------------------|
| Endereço    | Endereço de memória calculado (`base_addr + índice × 4`)         |
| Hex         | Instrução em hexadecimal                                          |
| Instrução   | Nome legível (`R add`, `I lw`, `NOP...`)                         |
| Observação  | Hazard detectado ou recálculo de offset de desvio                |

Linhas de NOP são destacadas em amarelo, linhas de branch com offset recalculado em verde.

No rodapé mostra estatísticas: instruções originais, NOPs inseridos e total.

### `_TAB_INFO` e `_DESCRIPTIONS`

Constantes que definem as abas disponíveis e suas descrições textuais. Permitem adicionar ou remover técnicas de análise sem mexer na lógica de construção das abas.

### `_DEMO_COMMENTS`

Dicionário que mapeia o índice de cada instrução da sequência Demo para um comentário explicativo. Exibido na coluna "Observação" da aba Demo para facilitar o entendimento didático.

---

## 11. `main.py`

### `readEachLineFromFile(filename) -> list[str]`

Lê o arquivo de instruções e normaliza cada linha para hex de 8 dígitos. Suporta três formatos:
- Hex puro (`00628233`)
- Hex com prefixo (`0x00628233`)
- Binário de 32 bits (`00000000011000101000001000110011`)

Ignora linhas vazias e comentários (`#` ou `//`). Em caso de linha inválida, avisa e continua (não aborta).

### `selectFile() -> str`

Abre uma janela nativa do sistema operacional para o usuário selecionar um arquivo. Usa `tkinter.filedialog` para isso. A janela do Tkinter é criada e destruída logo em seguida — ela existe apenas para hospedar o diálogo de seleção.

Se o usuário cancelar sem selecionar, retorna string vazia e `main()` usa o arquivo padrão `Instruções.txt`.

### `main()`

Orquestra tudo:

1. Abre o seletor de arquivo.
2. Lê e normaliza as instruções.
3. Cria um `InstructionDetails` para cada instrução (decodificação completa).
4. Detecta hazards e imprime no terminal.
5. Para cada técnica de resolução, calcula o sobrecusto em NOPs, salva o arquivo de saída e imprime as estatísticas.
6. Abre a interface gráfica.

**Sobrecusto** é calculado como:
```
sobrecusto = (número de NOPs inseridos / número de instruções originais) × 100%
```

Quanto maior o sobrecusto, mais ciclos desperdiçados o programa terá no pipeline — a técnica "Integrado com Forwarding" sempre terá o menor sobrecusto.

---

## Resumo visual do fluxo de dados

```
Arquivo .txt (hex/bin)
        |
        v
readEachLineFromFile()
        |  lista de strings hex
        v
InstructionDetails.__init__()
        |
        |-- setBinInstruction()     → "00628233" → "00000000011000101000001000110011"
        |-- setOpCode()             → binStr[-7:] → OpCode.R0110011
        |-- defineTypeForInstruction() → funct3 → InstructionType.RADD
        |-- SpecificPropertiesBuilder  → {Rs1: "00010 (2)", Rs2: "00011 (3)", Rd: "00001 (1)"}
        |
        v
list[InstructionDetails]
        |
        |── detect_data_hazards_*()    → list[HazardReport]  → impresso no terminal
        |── detect_control_hazards_*() → list[HazardReport]  → impresso no terminal
        |── insert_nops_*()            → list[InstructionRow] → salvo em output_*.txt
        |
        v
InstructionViewer (M1) ──botão──> PipelineViewer (M2)
```

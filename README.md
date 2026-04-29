# TV Program Neighbor Analysis

## 1. Definimi i problemit

Ky projekt merret me gjetjen e fqinjeve te programeve televizive nga nje instance JSON. Cdo instance permban nje liste te kanaleve, dhe secili kanal permban listen e programeve te tij. Qellimi eshte qe nga kjo strukture te gjenerohet nje vektor fqinjesie, ku gjatesia e vektorit eshte e barabarte me numrin total te programeve ne instance.

Nese instanca ka programe ne disa kanale, numri total i programeve llogaritet si:

```text
numri_total = programe_ne_Ch0 + programe_ne_Ch1 + programe_ne_Ch2 + ...
```

Output-i kryesor eshte:

```json
"neighbor_indices": [
  [1, 12],
  [],
  [5, 8, 9]
]
```

Kjo strukture lexohet keshtu:

- antari i pare i vektorit pershkruan fqinjet e programit me indeks `0`;
- antari i dyte pershkruan fqinjet e programit me indeks `1`;
- antari i trete pershkruan fqinjet e programit me indeks `2`;
- cdo liste e brendshme permban indekset e programeve qe konsiderohen fqinje.

Nese nje program nuk ka fqinje, lista e tij eshte bosh:

```json
[]
```

Kjo ne statistika llogaritet si `0` fqinje.

## 2. Qellimi i projektit

Qellimi nuk eshte implementimi i te gjitha constraints te problemit final te optimizimit, por definimi dhe gjenerimi i nje strukture fqinjesie qe mund te perdoret me vone nga metoda te tjera, p.sh. per swap, search neighborhood, heuristika ose algoritme optimizimi.

Per secilen instance projekti gjeneron:

- vektorin e fqinjeve per secilin program;
- numrin maksimal te fqinjeve per nje program;
- numrin minimal te fqinjeve per nje program;
- numrin mesatar te fqinjeve;
- madhesine e fajllit input;
- madhesine e fajllit output;
- memorien aktuale dhe memorien maksimale gjate ekzekutimit.

## 3. Struktura e projektit

```text
TV_Program_Neighbor_Analysis/
  main.py
  basic_neighbors.py
  advanced_neighbors.py
  valido.py
  instances/
  output/
  validation_reports/
  README.md
  project_documentation.pdf
```

Pershkrimi i fajllave kryesore:

- `main.py` eshte pika hyrese e programit. Lexon instancen, zgjedh variantin, gjeneron fqinjet, ruan output-in dhe shfaq statistikat/memorien.
- `basic_neighbors.py` permban variantin Basic, ku fqinjesia bazohet ne overlap kohor.
- `advanced_neighbors.py` permban variantin Advanced, ku fqinjesia bazohet ne nje dritare kohore me `Delta`.
- `valido.py` perdoret ndaras per te validuar output-in dhe per te gjeneruar raporte ndihmese.
- `instances/` permban instancat JSON.
- `output/` permban output-et e gjeneruara nga `main.py`.
- `validation_reports/` permban raportet e gjeneruara nga `valido.py`.

## 4. Formati i input-it

Input-i eshte nje fajll JSON qe permban kanale dhe programe. Struktura minimale qe perdoret nga projekti eshte:

```json
{
  "channels": [
    {
      "channel_id": 0,
      "programs": [
        {
          "program_id": "n1",
          "start": 540,
          "end": 600,
          "genre": "news",
          "score": 80
        }
      ]
    }
  ]
}
```

Fushat kryesore:

- `channel_id`: identifikuesi i kanalit;
- `program_id`: identifikuesi i programit;
- `start`: koha e fillimit ne minuta;
- `end`: koha e perfundimit ne minuta;
- `genre`: zhanri i programit, i ruajtur ashtu si vjen nga JSON;
- `score`: vlere ndihmese e programit, e ruajtur ne output per lexim dhe analizim.

## 5. Pergatitja e programeve

Programet ne input jane te ndara sipas kanaleve. Para se te gjenerohen fqinjet, `main.py` i sheshon te gjitha programet ne nje liste te vetme.

Shembull:

```text
Ch0: p0, p1
Ch1: p2, p3
Ch2: p4
```

kthehet ne:

```text
0 -> p0
1 -> p1
2 -> p2
3 -> p3
4 -> p4
```

Pas sheshimit, programet sortohen sipas kohes:

```python
programs.sort(key=lambda x: (x["start"], x["end"]))
```

Pastaj `global_index` rifreskohet. Ky indeks eshte baza e `neighbor_indices`.

## 6. Varianti Basic

Varianti Basic gjenerohet nga `basic_neighbors.py`.

Rregulla aktuale:

```text
B eshte fqinj i A nese:
1. B nuk eshte i njejti program me A;
2. B fillon ne te njejten kohe ose pas A;
3. A dhe B kane overlap kohor.
```

Kushti i overlap-it eshte:

```python
A.start < B.end and B.start < A.end
```

Ky variant eshte i thjeshte dhe sherben si baseline. Ai gjen programet qe mbivendosen ne kohe me programin aktual.

Shenim i rendesishem: kerkesa fillestare thote qe te Basic duhet te kontrollohet vetem overlap-i. Ne implementimin aktual ruhet edhe kushti qe kandidati te mos filloje para programit aktual. Kjo e ben fqinjesine te orientuar perpara ne kohe dhe shmang dyfishime simetrike, por duhet te arsyetohet ne raport ose te ndryshohet nese kerkohet interpretim strikt i overlap-it.

## 7. Varianti Advanced

Varianti Advanced gjenerohet nga `advanced_neighbors.py`.

Rregulla aktuale:

```text
B eshte fqinj i A nese:
1. B nuk eshte i njejti program me A;
2. B fillon ne te njejten kohe ose pas A;
3. B fillon brenda dritares [A.start, A.end + Delta].
```

Ne kod, `Delta` eshte vendosur ne `main.py`:

```python
DEFAULT_DELTA = 30
```

Pra, per nje program:

```text
A.start = 600
A.end = 660
Delta = 30
```

dritarja e fqinjesise eshte:

```text
[600, 690]
```

Cdo program kandidat qe fillon brenda kesaj dritareje konsiderohet fqinj, sipas rregullave te variantit Advanced.

Ky variant eshte me fleksibil se Basic, sepse nuk kerkon domosdoshmerisht overlap. Ai lejon edhe programe qe fillojne pak pas perfundimit te programit aktual, brenda `Delta`.

## 8. Ceshtja e programeve nga i njejti kanal

Implementimi aktual i lejon fqinjet nga i njejti kanal. Kjo ndodh sepse rregullat aktuale kontrollojne vetem kohen, jo `channel_id`.

Kjo eshte nje pike modelimi me rendesi:

- nese fqinjesia nenkupton vetem afersi kohore, atehere programet nga i njejti kanal mund te lejohen;
- nese fqinjesia perdoret per swap real mes alternativave televizive, atehere shpesh ka me shume kuptim qe programet nga i njejti kanal te perjashtohen.

Ne kete faze, `valido.py` i raporton fqinjet nga i njejti kanal si informacion, por nuk i trajton si gabim.

## 9. Formati i output-it

Output-i ruhet ne folderin `output/`.

Emrat jane te shkurter dhe deterministike:

```text
toy_basic.json
toy_advanced_delta30.json
```

Struktura kryesore e output-it:

```json
{
  "instance": "toy.json",
  "variant": "advanced",
  "delta": 30,
  "program_count": 5,
  "statistics": {
    "max_neighbors": 1,
    "min_neighbors": 0,
    "avg_neighbors": 0.6
  },
  "validation": {
    "valid": true,
    "errors": []
  },
  "programs": [
    {
      "index": 0,
      "program_id": "n1",
      "channel_id": 0,
      "start": 540,
      "end": 600,
      "genre": "news",
      "score": 80
    }
  ],
  "neighbor_indices": [
    [1],
    [],
    [3]
  ]
}
```

Fusha `programs` sherben per te interpretuar indekset. Fusha `neighbor_indices` eshte vektori kryesor i fqinjeve.

## 10. Statistikat

Per secilin run llogariten:

- `max_neighbors`: numri maksimal i fqinjeve qe ka ndonje program;
- `min_neighbors`: numri minimal i fqinjeve qe ka ndonje program;
- `avg_neighbors`: mesatarja e fqinjeve per program.

Shembull:

```text
neighbor counts = [1, 0, 1, 1, 0]
```

atehere:

```text
max = 1
min = 0
avg = (1 + 0 + 1 + 1 + 0) / 5 = 0.6
```

## 11. Matja e memories

`main.py` perdor `tracemalloc` per te matur memorien gjate ekzekutimit.

Ne console shfaqet:

```text
--- Memory ---
Instance file size: 1.57 MB
Output file size: 12.44 MB
Current memory: 85.32 MB
Peak memory: 143.77 MB
```

Kuptimi:

- `Instance file size`: madhesia e JSON-it input ne disk;
- `Output file size`: madhesia e output-it te gjeneruar ne disk;
- `Current memory`: memoria qe programi po mban ne momentin e matjes;
- `Peak memory`: maksimumi i memories se perdorur gjate ekzekutimit.

Per raportim, `Peak memory` eshte metrika me e rendesishme, sepse tregon kulmin e memories qe kerkohet per ate instance.

## 12. Validimi

Validimi kryhet ne dy nivele.

### 12.1 Validimi brenda `main.py`

Ky validim kontrollon qe:

- gjatesia e `neighbor_indices` te jete e barabarte me numrin e programeve;
- indekset e fqinjeve te jene numerike;
- indekset te jene brenda intervalit valid;
- programi te mos jete fqinj me vetveten;
- rregullat e variantit Basic ose Advanced te respektohen.

### 12.2 Validimi i avancuar me `valido.py`

`valido.py` ekzekutohet ndaras:

```powershell
python valido.py
```

Ai ofron 5 menyra validimi:

1. raport i vogel per nje program specifik;
2. timeline tekstual;
3. CSV ne `validation_reports/`;
4. validim automatik i gjithe output-it;
5. raport vizual HTML.

Raportet ruhen me emra te shkurter:

```text
toy_prog_0_summary.txt
toy_prog_0_timeline.txt
toy_prog_0_candidates.csv
toy_prog_0_visual.html
toy_automatic.txt
```

Validimi automatik eshte me i forte sepse rinderton fqinjet e pritur sipas rregullave dhe i krahason me output-in. Keshtu mund te identifikoje:

- fqinje qe mungojne;
- fqinje ekstra;
- indekse invalide;
- duplikate;
- renditje te ndryshme;
- fqinje nga i njejti kanal.

## 13. Si ekzekutohet projekti

Per gjenerim te fqinjeve:

```powershell
python main.py
```

Pastaj zgjidhet varianti:

```text
1. Basic variant - only overlap
2. Advanced variant - future time-window
```

Dhe zgjidhet instanca:

```text
0. Toy instance
1. croatia_tv
2. germany_tv
3. kosovo_tv
4. netherlands_tv
5. uk_tv
6. usa_tv
7. australia_iptv
8. france_iptv
9. spain_iptv
10. uk_iptv
11. us_iptv
12. singapore_pw
13. canada_pw
14. china_pw
15. youtube_gold
16. youtube_premium
```

Per validim:

```powershell
python valido.py
```

## 14. Kompleksiteti

Implementimi aktual ne `basic_neighbors.py` dhe `advanced_neighbors.py` perdor dy cikle te brendshme:

```text
for each program A:
    for each program B:
        kontrollo nese B eshte fqinj i A
```

Per `n` programe, kompleksiteti kohor eshte:

```text
O(n^2)
```

Kjo eshte e thjeshte per t'u kuptuar dhe e mire si baseline, por mund te behet e shtrenjte per instanca shume te medha.

Kompleksiteti memorik varet nga:

- lista e programeve;
- vektori `neighbor_indices`;
- numri total i fqinjeve te ruajtur.

Nese `E` eshte numri total i lidhjeve te fqinjesise, memoria per output-in eshte afersisht:

```text
O(n + E)
```

## 15. Mundesi optimizimi

Nje zgjidhje me efikase mund te perdore faktin qe programet jane te sortuara sipas `start`.

Per secilin program `A`, nuk ka nevoje te kontrollohen te gjitha programet `B`. Mund te kontrollohen vetem programet qe fillojne ne intervalin relevant:

- Basic: programet qe fillojne para `A.end`;
- Advanced: programet qe fillojne deri ne `A.end + Delta`.

Me binary search mund te gjendet kufiri i djathte i ketij intervali. Keshtu shmangen krahasimet e panevojshme me programe qe fillojne shume vone.

Kompleksiteti praktik mund te ulet ndjeshem, edhe pse ne rastin me te keq output-i mund te jete ende i madh.

## 16. Kufizime dhe vendime te hapura

Keto jane pikat qe duhen sqaruar ose mund te permiresohen:

- A duhet Basic te jete strikt vetem overlap, pa kushtin `candidate.start >= current.start`?
- A duhet te ndalohen fqinjet nga i njejti kanal?
- A duhet te ekzekutohen automatikisht te gjitha instancat per te dy variantet?
- A duhet te ruhet memoria edhe brenda JSON output-it, jo vetem ne console?
- A duhet te shtohet raport i pergjithshem per te gjitha instancat, me kohe/memorie/statistika ne nje CSV te vetem?

Keto pika jane te rendesishme per fazen studimore dhe per raportim final.

## 17. Perfundim

Projekti definon nje metode te qarte per gjenerimin e fqinjeve te programeve televizive nga instance JSON. Ai ofron dy variante, Basic dhe Advanced, gjeneron output te strukturuar, llogarit statistika kryesore, mat memorien e ekzekutimit dhe mundeson validim manual, automatik dhe vizual.

Zgjidhja aktuale eshte e pershtatshme si baze studimore, sepse eshte transparente, e testueshme dhe e lehte per t'u zgjeruar. Hapi tjeter natyral eshte optimizimi i algoritmit per instanca te medha dhe automatizimi i ekzekutimit per te gjitha instancat e datasetit.

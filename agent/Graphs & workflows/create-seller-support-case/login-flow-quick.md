# Support case — quick reference

Full tree: [MASTER_FLOW_TREE.md](MASTER_FLOW_TREE.md)

**Pehle:** [seller-login](../seller-central-login/MASTER_FLOW_TREE.md) ✅

```mermaid
flowchart LR
  L[seller-login OK] --> SC[support-case]
  SC --> S7[Badeja India]
  S7 --> CL[Case Log]
  CL --> F[Fill form]
  F -->|submit| OK[Done]
```

```powershell
cd agent
.\.venv\Scripts\python.exe -m mahika.cli support-case
.\.venv\Scripts\python.exe -m mahika.cli support-case --submit
```

---
created_at: 2025-12-27T10:38:55.755920
note_id: 1ce635fe-df19-4292-8018-237c09c0c541
document_ids: ["106c11a9-2d00-47f0-a3da-75b1d7e5a89f"]
note_style: short
llm_provider: gemini
llm_model: gemini-2.5-flash
tokens_used: 16312
---

Here's a combined, easy-to-read final note:

*   Centralized databases run on a single computer system, scaled vertically by making the machine more powerful.
*   Server systems often act as Transaction Servers (processing queries) or Data Servers (providing raw data for client processing).
*   Atomic instructions, like Test-And-Set, ensure safe access to shared resources in multi-user environments.
*   Parallel database systems use many processors and disks to handle large workloads and improve performance.
*   **Speedup** measures how much faster a fixed task runs on a larger system, while **Scaleup** measures performance when both problem and system size increase.
*   Common parallel architectures include **Shared Memory** (processors share memory), **Shared Disk** (processors share disks but have private memory), and **Shared Nothing** (each node has its own processor, memory, and disks, offering high scalability).
*   Distributed database systems spread data across multiple interconnected machines (sites), enabling users to access data from various locations.
*   Data replication in distributed systems enhances availability, allowing the system to continue functioning even if a site fails.
*   The Two-Phase Commit (2PC) protocol ensures that transactions spanning multiple sites in a distributed system are atomic.
*   Cloud computing provides on-demand resources through services like Infrastructure (IaaS), Platform (PaaS), and Software (SaaS).
*   Modern applications often use microservice architectures, deployed in containers and managed by orchestrators like Kubernetes, for flexibility and scalability.
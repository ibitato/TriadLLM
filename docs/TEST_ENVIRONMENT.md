# Test Environment

This document describes the hardware and model configuration used for TriadLLM integration testing.

## Overview

TriadLLM uses three local inference servers, each assigned a specific agent role:

| Role | Server | Model | Architecture |
|------|--------|-------|--------------|
| **Processor** | qbrain | Qwen3.6-27B (Q8_0) | AMD Radeon RX 7900 XTX × 2 |
| **Validator** | dgx | Nemotron-3-Super-120B (NVFP4) | NVIDIA DGX Spark (GB10) |
| **Orchestrator** | corsairai | Mistral-Small-4-119B (Q5_K_XL) | AMD Ryzen AI MAX+ 395 APU |

## Servers

### qbrain — Processor

The fastest model for initial answer generation. Qwen3.6-27B is small enough to run at full Q8_0 precision with speculative decoding enabled.

**Hardware:**
- CPU: AMD Ryzen 9 7900X (12 cores / 24 threads)
- RAM: 96 GB DDR5
- GPU: 2× AMD Radeon RX 7900 XTX (24 GB VRAM each, 48 GB total)
- Storage: 1.8 TB NVMe
- OS: Ubuntu 24.04.4 LTS

**Model Server:**
```
llama-server (llama.cpp, Vulkan backend)
  Model: unsloth/Qwen3.6-27B-MTP-GGUF:Q8_0
  Port: 8093
  Context: 262144 tokens
  GPU layers: 99 (fully offloaded)
  Flash attention: on
  KV cache: q8_0 (key + value)
  Speculative decoding: MTP (draft-n-max=6, p-min=0.75)
  Reasoning: on (deepseek format)
  Parallelism: 1 slot
  Temperature: 0.6
  Top-P: 0.95, Top-K: 20
```

**VRAM Usage:** ~21 GB / 24 GB (GPU 0)

---

### dgx — Validator

High-precision validation with massive context window. Nemotron-3-Super is a 120B MoE model (12B active) running in NVFP4 quantization with Multi-Token Prediction.

**Hardware:**
- Platform: NVIDIA DGX Spark
- CPU: ARM Cortex-X925 (10 cores / 20 threads)
- RAM: 128 GB unified memory (shared CPU/GPU via NVLink-C2C)
- GPU: NVIDIA GB10 (Grace Blackwell)
- Storage: 1.8 TB NVMe
- OS: Ubuntu 24.04.4 LTS
- Driver: NVIDIA 580.142, CUDA 13.0

**Model Server:**
```
vLLM (Docker, vllm/vllm-openai:cu130-nightly)
  Model: nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4
  Served as: nemotron-3-super
  Port: 8000
  Context: 131072 tokens
  Quantization: FP4 (NVFP4, Marlin backend)
  KV cache: FP8
  GPU memory utilization: 80%
  Speculative decoding: MTP (num_speculative_tokens=3)
  Chunked prefill: enabled
  Max concurrent sequences: 2
  Tensor parallelism: 1
  Reasoning parser: super_v3 (custom plugin)
  Tool calling: qwen3_coder parser
```

**GPU Memory Usage:** ~99 GB / 128 GB unified

---

### corsairai — Orchestrator

The largest model handles final synthesis. Mistral-Small-4-119B runs on the AMD Ryzen AI MAX+ 395's integrated GPU with 128 GB of shared memory.

**Hardware:**
- CPU/APU: AMD Ryzen AI MAX+ 395 (16 cores / 32 threads, integrated Radeon 8060S)
- RAM: 128 GB unified memory (shared with iGPU)
- Storage: 3.8 TB NVMe
- OS: Fedora Linux 43 (Server Edition)

**Model Server:**
```
llama-server (llama.cpp)
  Model: unsloth/Mistral-Small-4-119B-2603-GGUF:UD-Q5_K_XL
  Port: 8080
  Context: 262144 tokens
  GPU layers: 99 (fully offloaded to iGPU)
  Flash attention: off
  Memory mapping: disabled (--no-mmap)
  Chat template: mistral-small-4-reasoning.jinja
  Parallelism: 1 slot
  Context checkpoints: 32
  Cache prompt: enabled
  Temperature: 0.7
  Top-P: 0.95, Top-K: 40
  Threads: 32
```

---

## Role Assignment Rationale

| Role | Why this model |
|------|---------------|
| **Processor** (Qwen3.6-27B) | Fastest inference (~14-15 tok/s with MTP). Handles search results and produces initial answers quickly. Small enough for Q8_0 precision. |
| **Validator** (Nemotron-3-Super-120B) | 131K context window handles large search results without truncation. Low temperature (0.1) ensures factual validation. MoE efficiency (12B active) keeps latency reasonable. |
| **Orchestrator** (Mistral-Small-4-119B) | Largest dense model for deep synthesis. 119B parameters produce high-quality consolidated responses. Runs last so latency is less critical. |

## Performance Characteristics

Measured during E2E integration tests with real Firecrawl search:

| Metric | Value |
|--------|-------|
| Full pipeline (search + 3 agents) | ~230–270s |
| Firecrawl search (3 results) | ~1–2s |
| Search result size (sanitized) | ~60–95K chars |
| Final response length | ~2500–3000 chars |
| Total context per agent call | ~40K tokens max |

## External Services

| Service | Purpose | Auth |
|---------|---------|------|
| Firecrawl API v2 | Web search and scraping | `FIRECRAWL_API_KEY` env var |

No cloud LLM APIs are required for the default local configuration.

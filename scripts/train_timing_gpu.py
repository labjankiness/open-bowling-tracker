"""GPU Acceleration & Training Benchmark for Bowling Approach Timing Model.

Benchmarks multi-GPU training on available hardware:
- AMD Radeon RX 580 (DirectML / DirectX 12)
- NVIDIA GeForce RTX 5060 Ti (DirectML / DirectX 12)
- Host CPU Multi-threaded baseline (20 Cores)

Trains a Temporal 1D-CNN (TCN) Bowling Timing & Balance Model on pose kinematics.
"""

import os
import sys
import time
import json
import warnings
from pathlib import Path
from typing import Dict, Any, List

warnings.filterwarnings("ignore")

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torch_directml


# ---------------------------------------------------------
# 1. Bowling Kinematic Sequence Dataset
# ---------------------------------------------------------
class BowlingKinematicDataset(Dataset):
    """Synthetic kinematic dataset mimicking 2-handed lefty deliveries."""
    def __init__(self, num_samples: int = 1200, seq_len: int = 90, num_features: int = 16):
        self.num_samples = num_samples
        self.seq_len = seq_len
        self.num_features = num_features

        t = np.linspace(0, 1, seq_len)
        data = np.zeros((num_samples, seq_len, num_features), dtype=np.float32)
        phase_labels = np.zeros((num_samples, seq_len), dtype=np.int64)
        timing_targets = np.zeros((num_samples, 1), dtype=np.float32)
        balance_targets = np.zeros((num_samples, 1), dtype=np.float32)

        for i in range(num_samples):
            rel_idx = int(0.65 * seq_len + np.random.randint(-4, 5))
            apex_idx = int(0.40 * seq_len + np.random.randint(-3, 4))
            push_idx = int(0.20 * seq_len + np.random.randint(-3, 4))

            phase_labels[i, :push_idx] = 0
            phase_labels[i, push_idx:apex_idx] = 1
            phase_labels[i, apex_idx:rel_idx - 5] = 2
            phase_labels[i, rel_idx - 5:rel_idx] = 3
            phase_labels[i, rel_idx:rel_idx + 8] = 4
            phase_labels[i, rel_idx + 8:] = 5

            # Feature channels
            data[i, :, 0] = np.exp(-((t - (rel_idx / seq_len)) ** 2) / 0.04) * 0.55 + np.random.normal(0, 0.02, seq_len)
            data[i, :, 1] = (1 / (1 + np.exp(-(t - 0.5) * 10))) * 0.6 + np.random.normal(0, 0.02, seq_len)
            data[i, :, 2] = np.exp(-((t - (rel_idx / seq_len)) ** 2) / 0.02) * 0.85 + np.random.normal(0, 0.02, seq_len)
            data[i, :, 3] = np.exp(-((t - (apex_idx / seq_len)) ** 2) / 0.03) * 0.70 + np.random.normal(0, 0.02, seq_len)
            for f in range(4, num_features):
                data[i, :, f] = np.sin(t * np.pi * (f - 2)) * 0.3 + np.random.normal(0, 0.03, seq_len)

            timing_targets[i, 0] = float(0.55 + np.random.normal(0, 0.04))
            balance_targets[i, 0] = float(np.clip(85.0 + np.random.normal(0, 8.0), 50.0, 100.0))

        self.inputs = torch.from_numpy(data)
        self.phase_labels = torch.from_numpy(phase_labels)
        self.timing_targets = torch.from_numpy(timing_targets)
        self.balance_targets = torch.from_numpy(balance_targets)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        return (
            self.inputs[idx],
            self.phase_labels[idx],
            self.timing_targets[idx],
            self.balance_targets[idx],
        )


# ---------------------------------------------------------
# 2. Temporal Convolutional Network (TCN) for Bowling Kinematics
# ---------------------------------------------------------
class TCNBlock(nn.Module):
    def __init__(self, in_c, out_c, k=3, dilation=1):
        super().__init__()
        self.conv = nn.Conv1d(in_c, out_c, k, padding=(k // 2) * dilation, dilation=dilation)
        self.bn = nn.BatchNorm1d(out_c)
        self.act = nn.ReLU()

    def forward(self, x):
        return self.act(self.bn(self.conv(x)))


class BowlingTimingTCN(nn.Module):
    """Multi-layer Dilated Temporal ConvNet for phase & timing analysis."""
    def __init__(self, in_features: int = 16, num_phases: int = 6):
        super().__init__()
        self.encoder = nn.Sequential(
            TCNBlock(in_features, 32, k=3, dilation=1),
            TCNBlock(32, 64, k=3, dilation=2),
            TCNBlock(64, 128, k=5, dilation=4),
            TCNBlock(128, 128, k=5, dilation=8),
        )
        self.phase_head = nn.Conv1d(128, num_phases, kernel_size=1)
        self.timing_head = nn.Linear(128, 1)
        self.balance_head = nn.Linear(128, 1)

    def forward(self, x: torch.Tensor):
        # x: (batch, seq_len, in_features) -> transpose to (batch, in_features, seq_len)
        feat = self.encoder(x.transpose(1, 2))
        phase_logits = self.phase_head(feat).transpose(1, 2)  # (batch, seq_len, num_phases)
        pooled = feat.mean(dim=2)  # (batch, 128)
        timing_ratio = torch.sigmoid(self.timing_head(pooled))
        balance_score = self.balance_head(pooled)
        return phase_logits, timing_ratio, balance_score


# ---------------------------------------------------------
# 3. Hardware Discovery & Training Benchmark Runner
# ---------------------------------------------------------
def detect_available_devices() -> List[Dict[str, Any]]:
    devices = []

    # DirectML Devices (RX 580 and RTX 5060 Ti)
    try:
        if torch_directml.is_available():
            dml_count = torch_directml.device_count()
            for d in range(dml_count):
                dml_name = torch_directml.device_name(d).strip()
                is_rx = "580" in dml_name
                devices.append({
                    "id": f"directml:{d}",
                    "torch_device": torch_directml.device(d),
                    "name": dml_name,
                    "type": "AMD DirectML (DirectX 12)" if is_rx else "NVIDIA DirectML (DirectX 12)",
                    "vram_gb": 8.0 if is_rx else 16.0,
                })
    except Exception as e:
        print(f"[Warning] DirectML detection failed: {e}")

    # CPU Baseline
    import multiprocessing
    devices.append({
        "id": "cpu",
        "torch_device": torch.device("cpu"),
        "name": f"Host CPU ({multiprocessing.cpu_count()} Cores)",
        "type": "CPU Baseline",
        "vram_gb": 0.0,
    })

    return devices


def benchmark_device(
    device_info: Dict[str, Any],
    dataset: Dataset,
    batch_size: int = 32,
    num_epochs: int = 15,
) -> Dict[str, Any]:
    dev = device_info["torch_device"]
    name = device_info["name"]
    print(f"\n🚀 Benchmarking Device: {name} ({device_info['id']})")

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    model = BowlingTimingTCN().to(dev)

    criterion_phase = nn.CrossEntropyLoss()
    criterion_timing = nn.SmoothL1Loss()
    criterion_balance = nn.MSELoss()
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)

    # Warmup
    model.train()
    for batch_x, batch_phase, batch_timing, batch_balance in loader:
        bx = batch_x.to(dev)
        bphase = batch_phase.to(dev)
        btiming = batch_timing.to(dev)
        bbal = batch_balance.to(dev)
        p_logits, p_ratio, p_bal = model(bx)
        loss = (
            criterion_phase(p_logits.reshape(-1, 6), bphase.reshape(-1)) +
            criterion_timing(p_ratio, btiming) * 5.0 +
            criterion_balance(p_bal, bbal) * 0.01
        )
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        break

    total_samples = 0
    t_start = time.time()
    losses = []

    for epoch in range(num_epochs):
        ep_loss = 0.0
        n_batches = 0
        for batch_x, batch_phase, batch_timing, batch_balance in loader:
            bx = batch_x.to(dev)
            bphase = batch_phase.to(dev)
            btiming = batch_timing.to(dev)
            bbal = batch_balance.to(dev)

            optimizer.zero_grad()
            p_logits, p_ratio, p_bal = model(bx)
            loss = (
                criterion_phase(p_logits.reshape(-1, 6), bphase.reshape(-1)) +
                criterion_timing(p_ratio, btiming) * 5.0 +
                criterion_balance(p_bal, bbal) * 0.01
            )
            loss.backward()
            optimizer.step()

            ep_loss += float(loss.item())
            n_batches += 1
            total_samples += len(bx)

        losses.append(ep_loss / max(1, n_batches))

    total_time = time.time() - t_start
    throughput_samples_sec = round(total_samples / max(0.001, total_time), 1)
    throughput_frames_sec = round(throughput_samples_sec * 90, 1)
    ms_per_step = round((total_time / (num_epochs * len(loader))) * 1000, 2)

    print(f"  ✓ {num_epochs} Epochs Finished in {total_time:.2f}s")
    print(f"  ⚡ Throughput : {throughput_samples_sec} shots/sec ({throughput_frames_sec} kinematic fps)")
    print(f"  ⏱ Step Time  : {ms_per_step} ms/batch (Batch Size = {batch_size})")
    print(f"  📉 Final Loss : {losses[-1]:.4f}")

    return {
        "device_id": str(device_info["id"]),
        "device_name": name,
        "device_type": device_info["type"],
        "num_epochs": num_epochs,
        "batch_size": batch_size,
        "total_time_s": round(total_time, 2),
        "samples_per_sec": throughput_samples_sec,
        "kinematic_fps": throughput_frames_sec,
        "ms_per_step": ms_per_step,
        "final_loss": round(losses[-1], 4),
    }


def run_benchmark():
    print("=" * 70)
    print("🎳 BOWLING AI MODEL TRAINING & DUAL-GPU BENCHMARK SUITE")
    print("=" * 70)

    devices = detect_available_devices()
    print(f"Found {len(devices)} compute device(s):")
    for d in devices:
        vram_str = f"({d['vram_gb']} GB VRAM)" if d['vram_gb'] > 0 else ""
        print(f" • [{d['id']}] {d['name']} {vram_str} - {d['type']}")

    print("\nPreparing Kinematic Pose Sequence Dataset (1,200 Deliveries, 90 frames each)...")
    dataset = BowlingKinematicDataset(num_samples=1200, seq_len=90, num_features=16)

    results = []
    for d in devices:
        try:
            res = benchmark_device(d, dataset, batch_size=32, num_epochs=12)
            results.append(res)
        except Exception as e:
            print(f"  [Failed] Could not benchmark {d['name']}: {e}")

    print("\n" + "=" * 70)
    print("🏆 FINAL GPU & CPU BENCHMARK COMPARISON TABLE")
    print("=" * 70)
    header = f"{'Device':<28} | {'Type':<22} | {'Speed (Shots/s)':<15} | {'Latency'}"
    print(header)
    print("-" * 70)

    cpu_speed = next((r["samples_per_sec"] for r in results if "cpu" in r["device_id"]), 1.0)

    for r in results:
        speedup = round(r["samples_per_sec"] / max(0.1, cpu_speed), 1)
        speedup_str = f"({speedup}x CPU)" if "cpu" not in r["device_id"] else "(1.0x Baseline)"
        row = f"{r['device_name'][:27]:<28} | {r['device_type'][:21]:<22} | {r['samples_per_sec']:<5} {speedup_str:<9} | {r['ms_per_step']} ms/step"
        print(row)

    print("=" * 70)

    report_file = PROJECT_ROOT / "data" / "gpu_benchmark_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📊 Benchmark report saved to: {report_file}")

    # Use os._exit to bypass DirectML clean-up issue in WSL
    os._exit(0)


if __name__ == "__main__":
    run_benchmark()

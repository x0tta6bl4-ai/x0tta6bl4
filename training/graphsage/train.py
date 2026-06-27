import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, GATConv
from torch_geometric.data import Data
import numpy as np
import os

class MeshGraphSAGE(nn.Module):
    def __init__(self, in_channels=4, hidden_channels=128, out_channels=1, heads=4):
        super(MeshGraphSAGE, self).__init__()
        # GraphSAGE with Attention (simulated via GAT for attention mechanism)
        self.conv1 = GATConv(in_channels, hidden_channels, heads=heads, concat=False)
        self.conv2 = SAGEConv(hidden_channels, hidden_channels)
        self.fc = nn.Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        return torch.sigmoid(self.fc(x))

def generate_synthetic_data(num_nodes=500):
    # Features: [node_degree, latency_p99, packet_loss_rate, rssi_avg]
    x = torch.rand((num_nodes, 4), dtype=torch.float32)
    # Simulate RSSI (-30 to -90) normalized
    x[:, 3] = (x[:, 3] * 60) - 90
    
    # Random edges (approx 10 degrees per node)
    edge_index = torch.randint(0, num_nodes, (2, num_nodes * 10), dtype=torch.long)
    
    # Labels: 1 for good route, 0 for bad route (based on latency and loss threshold)
    y = ((x[:, 1] < 0.5) & (x[:, 2] < 0.1)).float().view(-1, 1)
    
    return Data(x=x, edge_index=edge_index, y=y)

def train():
    print("Training GraphSAGE v2 model with 4 attention heads on 500-node synthetic dataset...")
    model = MeshGraphSAGE()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.BCELoss()
    
    data = generate_synthetic_data(500)
    
    model.train()
    for epoch in range(200):
        optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        loss = criterion(out, data.y)
        loss.backward()
        optimizer.step()
        
        if epoch % 50 == 0:
            pred = (out > 0.5).float()
            acc = (pred == data.y).sum().item() / data.num_nodes
            print(f'Epoch {epoch}, Loss: {loss.item():.4f}, Accuracy: {acc:.4f}')

    # Validate target accuracy 93-95%
    model.eval()
    val_data = generate_synthetic_data(100)
    out = model(val_data.x, val_data.edge_index)
    pred = (out > 0.5).float()
    val_acc = (pred == val_data.y).sum().item() / val_data.num_nodes
    print(f'Validation Accuracy: {val_acc:.4f} (Target: >0.93)')

    # Export to ONNX
    os.makedirs('/mnt/projects/models', exist_ok=True)
    dummy_x = torch.randn(500, 4)
    dummy_edge_index = torch.randint(0, 500, (2, 2000))
    torch.onnx.export(model, (dummy_x, dummy_edge_index), 
                      "/mnt/projects/models/graphsage_v2_attention.onnx", 
                      input_names=['x', 'edge_index'], 
                      output_names=['output'],
                      dynamic_axes={'x': {0: 'num_nodes'}, 'edge_index': {1: 'num_edges'}, 'output': {0: 'num_nodes'}})
    print("Exported to /mnt/projects/models/graphsage_v2_attention.onnx")

if __name__ == '__main__':
    train()
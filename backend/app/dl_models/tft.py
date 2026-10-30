import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class GatedLinearUnit(nn.Module):
    def __init__(self, input_size: int, output_size: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_size, output_size)
        self.fc2 = nn.Linear(input_size, output_size)
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(output_size)

    def forward(self, x: torch.Tensor, residual: torch.Tensor = None) -> torch.Tensor:
        sig = torch.sigmoid(self.fc2(x))
        out = self.dropout(self.fc1(x)) * sig
        if residual is not None and residual.size(-1) == out.size(-1):
            out = out + residual
        return self.layer_norm(out)


class GatedResidualNetwork(nn.Module):
    def __init__(
        self, input_size: int, hidden_size: int,
        output_size: int = None, context_size: int = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.output_size = output_size or input_size
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.elu = nn.ELU()
        self.context_proj = nn.Linear(context_size, hidden_size, bias=False) if context_size else None
        self.fc2 = nn.Linear(hidden_size, self.output_size)
        self.glu = GatedLinearUnit(self.output_size, self.output_size, dropout)
        self.residual_proj = (
            nn.Linear(input_size, self.output_size) if input_size != self.output_size else None
        )

    def forward(self, x: torch.Tensor, context: torch.Tensor = None) -> torch.Tensor:
        residual = self.residual_proj(x) if self.residual_proj else x
        hidden = self.fc1(x)
        if self.context_proj is not None and context is not None:
            hidden = hidden + self.context_proj(context)
        hidden = self.elu(hidden)
        hidden = self.fc2(hidden)
        return self.glu(hidden, residual)


class VariableSelectionNetwork(nn.Module):
    def __init__(
        self, input_size: int, num_inputs: int,
        hidden_size: int, context_size: int = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_inputs = num_inputs

        self.flattened_grn = GatedResidualNetwork(
            input_size=num_inputs * input_size,
            hidden_size=hidden_size,
            output_size=num_inputs,
            context_size=context_size,
            dropout=dropout,
        )
        self.single_grns = nn.ModuleList([
            GatedResidualNetwork(
                input_size=input_size,
                hidden_size=hidden_size,
                output_size=hidden_size,
                dropout=dropout,
            )
            for _ in range(num_inputs)
        ])

    def forward(self, x: torch.Tensor, context: torch.Tensor = None) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape
        flatten = x.reshape(batch_size * seq_len, -1)

        sparse_weights = self.flattened_grn(flatten, context.repeat(seq_len, 1) if context is not None else None)
        sparse_weights = torch.softmax(sparse_weights, dim=-1).unsqueeze(-1)

        per_input_size = x.shape[-1] // self.num_inputs
        processed = []
        for i, grn in enumerate(self.single_grns):
            start = i * per_input_size
            end = start + per_input_size
            chunk = x[:, :, start:end].reshape(batch_size * seq_len, -1)
            processed.append(grn(chunk))

        processed = torch.stack(processed, dim=1)
        sparse_weights_exp = sparse_weights.view(batch_size * seq_len, self.num_inputs, 1)
        combined = (sparse_weights_exp * processed).sum(dim=1)
        return combined.view(batch_size, seq_len, self.hidden_size)


class InterpretableMultiHeadAttention(nn.Module):
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)
        self.w_o = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, mask=None):
        batch_size = q.size(0)
        q = self.w_q(q).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        k = self.w_k(k).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        v = self.w_v(v).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)

        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_k)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        attn = self.dropout(torch.softmax(scores, dim=-1))

        context = torch.matmul(attn, v)
        context = context.transpose(1, 2).contiguous().view(batch_size, -1, self.d_model)
        return self.w_o(context), attn


class TemporalFusionTransformer(nn.Module):
    """
    Temporal Fusion Transformer 股票预测模型

    核心组件:
    1. Variable Selection Network - 自动选择重要特征
    2. Gated Residual Network - 信息门控
    3. Interpretable Multi-Head Attention - 可解释注意力
    4. 静态协变量编码器
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 128,
        num_heads: int = 4,
        num_encoder_layers: int = 2,
        num_decoder_layers: int = 2,
        dropout: float = 0.1,
        attention_dropout: float = 0.1,
        predict_steps: int = 1,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.predict_steps = predict_steps
        self.input_size = input_size

        self.input_projection = nn.Linear(input_size, hidden_size)
        self.input_gate = GatedLinearUnit(hidden_size, hidden_size, dropout)

        num_var_groups = min(input_size, 16)
        self.var_selection = VariableSelectionNetwork(
            input_size=hidden_size // num_var_groups,
            num_inputs=num_var_groups,
            hidden_size=hidden_size,
            context_size=hidden_size,
            dropout=dropout,
        )

        self.static_encoder = GatedResidualNetwork(
            input_size=hidden_size,
            hidden_size=hidden_size,
            output_size=hidden_size,
            dropout=dropout,
        )

        self.lstm_encoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_encoder_layers,
            batch_first=True,
            dropout=dropout if num_encoder_layers > 1 else 0,
        )
        self.lstm_decoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_decoder_layers,
            batch_first=True,
            dropout=dropout if num_decoder_layers > 1 else 0,
        )

        self.post_lstm_gate = GatedLinearUnit(hidden_size, hidden_size, dropout)

        self.attention = InterpretableMultiHeadAttention(
            d_model=hidden_size,
            num_heads=num_heads,
            dropout=attention_dropout,
        )
        self.post_attn_gate = GatedLinearUnit(hidden_size, hidden_size, dropout)
        self.post_attn_norm = nn.LayerNorm(hidden_size)

        self.position_wise_ff = GatedResidualNetwork(
            input_size=hidden_size,
            hidden_size=hidden_size * 4,
            output_size=hidden_size,
            dropout=dropout,
        )
        self.output_gate = GatedLinearUnit(hidden_size, hidden_size, dropout)
        self.output_norm = nn.LayerNorm(hidden_size)

        self.output_projection = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, predict_steps),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape

        projected = self.input_projection(x)
        gated_input = self.input_gate(projected)

        static_context = self.static_encoder(gated_input.mean(dim=1))

        num_groups = min(self.input_size, 16)
        group_size = self.hidden_size // num_groups
        adjusted = gated_input[:, :, :num_groups * group_size]
        selected = self.var_selection(adjusted, static_context)

        encoder_out, (hidden, cell) = self.lstm_encoder(selected)
        decoder_out, _ = self.lstm_decoder(encoder_out, (hidden, cell))

        temporal = self.post_lstm_gate(decoder_out, selected)

        attn_out, attn_weights = self.attention(temporal, temporal, temporal)
        attn_out = self.post_attn_gate(attn_out, temporal)
        attn_out = self.post_attn_norm(attn_out)

        ff_out = self.position_wise_ff(attn_out)
        output = self.output_gate(ff_out, attn_out)
        output = self.output_norm(output)

        final_hidden = output[:, -1, :]
        prediction = self.output_projection(final_hidden)
        return prediction

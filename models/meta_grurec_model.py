# import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
# from easydict import EasyDict
from .base import MetaLinearLayer, MetaBERTEmbedding, extract_top_level_dict, MetaGRUModel


class MetaGRU4REC(nn.Module):
    """
        GRU4REC for regression task. 
    """

    def __init__(self, args):
        args.device = "cpu"
        super(MetaGRU4REC, self).__init__()
        self.hidden_size = args.gru4rec_hidden_size
        self.n_layers = args.gru4rec_n_layers
        max_len = args.max_seq_len-1
        dropout = args.bert_dropout
        num_items = args.num_items
        vocab_size = num_items + 2
        self.device = args.device
        self.embedding_dim = args.gru4rec_embedding_dim
        self.embedding = MetaBERTEmbedding(
            vocab_size=vocab_size,  embed_size=self.embedding_dim, max_len=max_len, dropout=dropout, needs_position=False)
        self.gru = MetaGRUModel(
            self.embedding_dim, self.hidden_size, self.n_layers, self.hidden_size)
        self.relu = nn.ReLU()

        self.out_layer = MetaLinearLayer(self.hidden_size, 1, use_bias=True)

    def forward(self, inputs, params=None):

        if params is not None:
            params = {key: value for key, value in params.items()}
            param_dict = extract_top_level_dict(current_dict=params)
            embedding_params = param_dict['embedding']
            gru_params = param_dict['gru']
            out_params = param_dict['out_layer']

        else:
            embedding_params = None
            gru_params = None
            out_params = None

        x = self.embedding(inputs, params=embedding_params)
        gru_out, h_n = self.gru(x, params=gru_params)

        # out = gru_out[:, -1, :]

        out = self.relu(gru_out)

        out = self.out_layer(out, params=out_params)

        b, t, d = out.shape
        out = out.view(b, -1)

        return 0.1 + torch.sigmoid(out)

    def zero_grad(self, params=None):
        if params is None:
            for param in self.parameters():
                if (
                    param.requires_grad == True
                    and param.grad is not None
                    and torch.sum(param.grad) > 0
                ):
                    # print(param.grad)
                    param.grad.zero_()
        else:
            for name, param in params.items():
                if (
                    param.requires_grad == True
                    and param.grad is not None
                    and torch.sum(param.grad) > 0
                ):
                    # print(param.grad)
                    param.grad.zero_()
                    params[name].grad = None

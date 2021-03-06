# 
# Copyright (c) 2017-2019 Minato Sato
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

import nnabla as nn
import nnabla.functions as F
import nnabla.parametric_functions as PF
import numpy as np

from typing import Optional
from typing import Tuple

@PF.parametric_function_api('simple_rnn')
def simple_rnn(inputs: nn.Variable, units: int, mask: Optional[nn.Variable] = None,
               return_sequences: bool = False, fix_parameters=False) -> nn.Variable:
    '''
    A vanilla recurrent neural network layer
    Args:
        inputs (nnabla.Variable): A shape of [batch_size, length, embedding_size].
        units (int): Dimensionality of the output space.
        mask (nnabla.Variable): A shape of [batch_size, length, 1].
        return_sequences (bool): Whether to return the last output. in the output sequence, or the full sequence.
        fix_parameters (bool): Fix parameters (Set need_grad=False).
    Returns:
        nn.Variable: A shape [batch_size, length, units]
        or
        nn.Variable: A shape [batch_size units].
    '''

    hs = []
    batch_size, length, embedding_size = inputs.shape
    h0 = F.constant(0, shape=(batch_size, units))

    h = h0

    if mask is None:
        mask = F.constant(1, shape=(batch_size, length, 1))

    for x, cond in zip(F.split(inputs, axis=1), F.split(mask, axis=1)):
        h_t = F.tanh(PF.affine(F.concatenate(x, h, axis=1), units, fix_parameters=fix_parameters))
        h = where(cond, h_t, h)
        hs.append(h)

    if return_sequences:
        hs = F.stack(*hs, axis=1)
        return hs
    else:
        return hs[-1]

def lstm_cell(x: nn.Variable, c: nn.Variable, h: nn.Variable) -> nn.Variable:
    batch_size, units = c.shape
    _hidden = PF.affine(F.concatenate(x, h, axis=1), 4*units)

    a            = F.tanh   (_hidden[:, units*0: units*1])
    input_gate   = F.sigmoid(_hidden[:, units*1: units*2])
    forgate_gate = F.sigmoid(_hidden[:, units*2: units*3])
    output_gate  = F.sigmoid(_hidden[:, units*3: units*4])

    cell = input_gate * a + forgate_gate * c
    hidden = output_gate * F.tanh(cell)
    return cell, hidden

@PF.parametric_function_api('lstm')
def lstm(inputs: nn.Variable, units: int, mask: Optional[nn.Variable] = None, initial_state: Tuple[nn.Variable, nn.Variable] = None,
         return_sequences: bool = False, return_state: bool = False, fix_parameters: bool = False) -> nn.Variable:
    '''
    A long short-term memory
    Args:
        inputs (nnabla.Variable): A shape of [batch_size, length, embedding_size].
        units (int): Dimensionality of the output space.
        mask (nnabla.Variable): A shape of [batch_size, length].
        initial_state ([nnabla.Variable, nnabla.Variable]): A tuple of an initial cell and an initial hidden state.
        return_sequences (bool): Whether to return the last output. in the output sequence, or the full sequence.
        return_state (bool): Whether to return the last state which is consist of the cell and the hidden state.
        fix_parameters (bool): Fix parameters (Set need_grad=False).
    Returns:
        nn.Variable: A shape [batch_size, length, units].
        or
        nn.Variable: A shape [batch_size units]
    '''
    
    batch_size, length, embedding_size = inputs.shape

    if initial_state is None:
        c0 = F.constant(0, shape=(batch_size, units))
        h0 = F.constant(0, shape=(batch_size, units))
    else:
        assert type(initial_state) is tuple or type(initial_state) is list, \
               'initial_state must be a typle or a list.'
        assert len(initial_state) == 2, \
               'initial_state must have only two states.'

        c0, h0 = initial_state

        assert c0.shape == h0.shape, 'shapes of initial_state must be same.'
        assert c0.shape[0] == batch_size, \
               'batch size of initial_state ({0}) is different from that of inputs ({1}).'.format(c0.shape[0], batch_size)
        assert c0.shape[1] == units, \
               'units size of initial_state ({0}) is different from that of units of args ({1}).'.format(c0.shape[1], units)

    cell = c0
    hidden = h0

    hs = []

    if mask is None:
        mask = F.constant(1, shape=(batch_size, length, 1))
    for x, cond in zip(F.split(inputs, axis=1), F.split(mask, axis=1)):
        cell_t, hidden_t = lstm_cell(x, cell, hidden)
        cell = where(cond, cell_t, cell)
        hidden = where(cond, hidden_t, hidden)
        hs.append(hidden)

    if return_sequences:
        ret = F.stack(*hs, axis=1)
    else:
        ret = hs[-1]

    if return_state:
        return ret, cell, hidden
    else:
        return ret


@PF.parametric_function_api('highway')
def highway(x: nn.Variable, fix_parameters: bool = False) -> nn.Variable:
    '''
    A densely connected highway network layer
    Args:
        x (nnabla.Variable): A shape of [batch_size, units]
        fix_parameters (bool): Fix parameters (Set need_grad=False).
    Returns:
        nn.Variable: A shape [batch_size, units].
    '''
    batch_size, in_out_size = x.shape

    with nn.parameter_scope('plain'):
        out_plain = F.relu(PF.affine(x, in_out_size, fix_parameters=fix_parameters))
    with nn.parameter_scope('transform'):
        out_transform = F.sigmoid(PF.affine(x, in_out_size, fix_parameters=fix_parameters))
    y = out_plain * out_transform + x * (1 - out_transform)
    return y


def where(condition: nn.Variable, x:nn.Variable, y: nn.Variable) -> nn.Variable:
    '''
    This function returns x if condition is 1, and y if condition is 0.
    Args:
        condition (nnabla.Variable): A shape of (batch_size, 1)
        x (nnabla.Variable): A shape of (batch_size, embedding_size)
        y (nnabla.Variable): A shape of (batch_size, embedding_size)
    '''
    if x.ndim == 1:
        true_condition = F.reshape(condition, shape=list(condition.shape)+[1])
    else:
        true_condition = condition
    false_condition = F.constant(1, shape=true_condition.shape) - true_condition
    return true_condition * x + false_condition * y

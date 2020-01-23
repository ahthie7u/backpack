from math import sqrt

from torch import diag, diag_embed, multinomial, ones_like, softmax
from torch import sqrt as torchsqrt
from torch.nn import CrossEntropyLoss
from torch.nn.functional import one_hot

from ...utils.einsum import einsum
from .basederivatives import BaseDerivatives
from backpack.utils.unsqueeze import hmp_unsqueeze_if_missing_dim


class CrossEntropyLossDerivatives(BaseDerivatives):
    def get_module(self):
        return CrossEntropyLoss

    def sqrt_hessian(self, module, g_inp, g_out):
        probs = self.get_probs(module)
        tau = torchsqrt(probs)
        Id = diag_embed(ones_like(probs))
        Id_tautau = Id - einsum("ni,nj->nij", tau, tau)
        sqrt_H = einsum("ni,nij->nij", tau, Id_tautau)

        if module.reduction == "mean":
            sqrt_H /= sqrt(module.input0.shape[0])

        return sqrt_H

    def make_sqrt_hessian_sampled_fn(self, mc_samples=1):
        def _sqrt_hessian_sampled_fn(module, g_inp, g_out):
            return self.sqrt_hessian_sampled(module, g_inp, g_out, mc_samples)

        return _sqrt_hessian_sampled_fn

    def sqrt_hessian_sampled(self, module, g_inp, g_out, mc_samples=1):
        M = mc_samples
        C = module.input0.shape[1]

        probs = self.get_probs(module)
        probs_unsqueezed = probs.unsqueeze(-1).repeat(1, 1, M)

        classes = one_hot(multinomial(probs, M, replacement=True), num_classes=C)
        classes = classes.transpose(1, 2).float()

        sqrt_mc_h = (probs_unsqueezed - classes) / sqrt(M)

        if module.reduction == "mean":
            sqrt_mc_h /= sqrt(module.input0.shape[0])

        return sqrt_mc_h

    def sum_hessian(self, module, g_inp, g_out):
        probs = self.get_probs(module)
        sum_H = diag(probs.sum(0)) - einsum("bi,bj->ij", (probs, probs))

        if module.reduction == "mean":
            sum_H /= module.input0.shape[0]

        return sum_H

    def hessian_matrix_product(self, module, g_inp, g_out):
        """Multiplication of the input Hessian with a matrix."""
        probs = self.get_probs(module)

        @hmp_unsqueeze_if_missing_dim(mat_dim=3)
        def hmp(mat):
            Hmat = einsum("bi,bic->bic", (probs, mat)) - einsum(
                "bi,bj,bjc->bic", (probs, probs, mat)
            )

            if module.reduction == "mean":
                Hmat /= module.input0.shape[0]

            return Hmat

        return hmp

    def hessian_is_psd(self):
        return True

    def get_probs(self, module):
        return softmax(module.input0, dim=1)

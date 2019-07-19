from torch import zeros, prod
from torch.nn import MaxPool2d
from torch.nn.functional import max_pool2d
from ...utils import conv as convUtils
from .basederivatives import BaseDerivatives

from .utils import jmp_unsqueeze_if_missing_dim


class MaxPool2DDerivatives(BaseDerivatives):
    def get_module(self):
        return MaxPool2d

    def get_pooling_idx(self, module):
        # TODO: Do not recompute but get from forward pass of module
        _, pool_idx = max_pool2d(
            module.input0,
            kernel_size=module.kernel_size,
            stride=module.stride,
            padding=module.padding,
            dilation=module.dilation,
            return_indices=True,
            ceil_mode=module.ceil_mode)
        return pool_idx

    def hessian_is_zero(self):
        return True

    # Jacobian-matrix product
    @jmp_unsqueeze_if_missing_dim(mat_dim=3)
    def jac_mat_prod(self, module, grad_input, grad_output, mat):
        convUtils.check_sizes_input_jac(mat, module)
        mat_as_pool = self.__reshape_for_pooling_in(mat, module)
        jmp_as_pool = self.__apply_jacobian_of(module, mat_as_pool)
        return self.__reshape_for_matmul(jmp_as_pool, module)

    def __reshape_for_pooling_in(self, mat, module):
        num_classes = mat.size(-1)
        batch, channels, in_x, in_y = module.input0.size()
        return mat.view(batch, channels, in_x * in_y, num_classes)

    def __reshape_for_matmul(self, mat, module):
        batch = module.output_shape[0]
        out_features = prod(module.output_shape) / batch
        num_classes = mat.size(-1)
        return mat.view(batch, out_features, num_classes)

    def __apply_jacobian_of(self, module, mat):
        batch, channels, out_x, out_y = module.output_shape
        num_classes = mat.shape[-1]

        pool_idx = self.get_pooling_idx(module)
        pool_idx = pool_idx.view(batch, channels, out_x * out_y)
        pool_idx = pool_idx.unsqueeze(-1).expand(-1, -1, -1, num_classes)

        return mat.gather(2, pool_idx)

    # Transposed Jacobian-matrix product
    @jmp_unsqueeze_if_missing_dim(mat_dim=3)
    def jac_t_mat_prod(self, module, grad_input, grad_output, mat):
        convUtils.check_sizes_input_jac_t(mat, module)
        mat_as_pool = self.__reshape_for_pooling_out(mat, module)
        jmp_as_pool = self.__apply_jacobian_t_of(module, mat_as_pool)
        return self.__reshape_for_matmul_t(jmp_as_pool, module)

    def __reshape_for_pooling_out(self, mat, module):
        num_classes = mat.size(-1)
        batch, channels, out_x, out_y = module.output_shape
        return mat.view(batch, channels, out_x * out_y, num_classes)

    def __reshape_for_matmul_t(self, mat, module):
        batch = module.output_shape[0]
        in_features = module.input0.numel() / batch
        num_classes = mat.size(-1)
        return mat.view(batch, in_features, num_classes)

    def __apply_jacobian_t_of(self, module, mat):
        batch, channels, out_x, out_y = module.output_shape
        _, _, in_x, in_y = module.input0.size()
        num_classes = mat.shape[-1]

        result = zeros(
            batch, channels, in_x * in_y, num_classes, device=mat.device)

        pool_idx = self.get_pooling_idx(module)
        pool_idx = pool_idx.view(batch, channels, out_x * out_y)
        pool_idx = pool_idx.unsqueeze(-1).expand(-1, -1, -1, num_classes)
        result.scatter_add_(2, pool_idx, mat)
        return result

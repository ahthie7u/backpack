from backpack.utils.utils import einsum
from backpack.new_extensions.firstorder import FirstOrderExtension


class BatchL2Linear(FirstOrderExtension):
    def __init__(self):
        super().__init__(params=["bias", "weight"])

    def bias(self, ext, module, grad_input, grad_output, backproped):
        return (grad_output[0] ** 2).sum(1)

    def weight(self, ext, module, grad_input, grad_output, backproped):
        return einsum('bi,bj->b', (grad_output[0] ** 2, module.input0 ** 2))


class BatchL2LinearConcat(FirstOrderExtension):
    def __init__(self):
        super().__init__(params=["weight"])

    def weight(self, ext, module, grad_input, grad_output, backproped):
        input = module.homogeneous_input()
        return einsum('bi,bj->b', (grad_output[0] ** 2, input ** 2))

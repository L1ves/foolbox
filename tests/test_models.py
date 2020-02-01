import pytest
import eagerpy as ep
import numpy as np
import copy

import foolbox.ext.native as fbn


def test_bounds(fmodel_and_data):
    fmodel, x, y = fmodel_and_data
    min_, max_ = fmodel.bounds
    assert min_ < max_
    assert (x >= min_).all()
    assert (x <= max_).all()


def test_forward_unwrapped(fmodel_and_data):
    fmodel, x, y = fmodel_and_data
    logits = ep.astensor(fmodel(x.raw))
    assert logits.ndim == 2
    assert len(logits) == len(x) == len(y)
    _, num_classes = logits.shape
    assert (y >= 0).all()
    assert (y < num_classes).all()


def test_forward_wrapped(fmodel_and_data):
    fmodel, x, y = fmodel_and_data
    assert ep.istensor(x)
    logits = fmodel(x)
    assert ep.istensor(logits)
    assert logits.ndim == 2
    assert len(logits) == len(x) == len(y)
    _, num_classes = logits.shape
    assert (y >= 0).all()
    assert (y < num_classes).all()


def test_pytorch_training_warning(request):
    backend = request.config.option.backend
    if backend != "pytorch":
        pytest.skip()

    import torch

    class Model(torch.nn.Module):
        def forward(self, x):
            return x

    model = Model().train()
    bounds = (0, 1)
    with pytest.warns(UserWarning):
        fbn.PyTorchModel(model, bounds=bounds, device="cpu")


@pytest.mark.parametrize("bounds", [(0, 1), (-1.0, 1.0), (0, 255), (-32768, 32767)])
def test_transform_bounds(fmodel_and_data, bounds):
    fmodel1, x, y = fmodel_and_data
    logits1 = fmodel1(x)
    min1, max1 = fmodel1.bounds

    fmodel2 = fmodel1.transform_bounds(bounds)
    min2, max2 = fmodel2.bounds
    x2 = (x - min1) / (max1 - min1) * (max2 - min2) + min2
    logits2 = fmodel2(x2)

    np.testing.assert_allclose(logits1.numpy(), logits2.numpy(), rtol=1e-4, atol=1e-4)

    # to make sure fmodel1 is not changed in-place
    logits1b = fmodel1(x)
    np.testing.assert_allclose(logits1.numpy(), logits1b.numpy(), rtol=2e-6)

    fmodel1c = fmodel2.transform_bounds(fmodel1.bounds)
    logits1c = fmodel1c(x)
    np.testing.assert_allclose(logits1.numpy(), logits1c.numpy(), rtol=1e-4, atol=1e-4)


@pytest.mark.parametrize("bounds", [(0, 1), (-1.0, 1.0), (0, 255), (-32768, 32767)])
def test_transform_bounds_inplace(fmodel_and_data, bounds):
    fmodel, x, y = fmodel_and_data
    fmodel = copy.copy(fmodel)  # to avoid interference with other tests

    if not isinstance(fmodel, fbn.models.base.ModelWithPreprocessing):
        pytest.skip()
    logits1 = fmodel(x)
    min1, max1 = fmodel.bounds

    fmodel.transform_bounds(bounds, inplace=True)
    min2, max2 = fmodel.bounds
    x2 = (x - min1) / (max1 - min1) * (max2 - min2) + min2
    logits2 = fmodel(x2)

    np.testing.assert_allclose(logits1.numpy(), logits2.numpy(), rtol=1e-4, atol=1e-4)


def test_preprocessing(fmodel_and_data):
    fmodel, x, y = fmodel_and_data
    if not isinstance(fmodel, fbn.models.base.ModelWithPreprocessing):
        pytest.skip()

    preprocessing = dict(mean=[3, 3, 3], std=[5, 5, 5], axis=-3)
    fmodel = fbn.models.base.ModelWithPreprocessing(
        fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
    )

    preprocessing = dict(mean=[3, 3, 3], axis=-3)
    fmodel = fbn.models.base.ModelWithPreprocessing(
        fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
    )

    preprocessing = dict(mean=np.array([3, 3, 3]), axis=-3)
    fmodel = fbn.models.base.ModelWithPreprocessing(
        fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
    )

    # std -> foo
    preprocessing = dict(mean=[3, 3, 3], foo=[5, 5, 5], axis=-3)
    with pytest.raises(ValueError):
        fmodel = fbn.models.base.ModelWithPreprocessing(
            fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
        )

    # axis positive
    preprocessing = dict(mean=[3, 3, 3], std=[5, 5, 5], axis=1)
    with pytest.raises(ValueError):
        fmodel = fbn.models.base.ModelWithPreprocessing(
            fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
        )

    preprocessing = dict(mean=3, std=5)
    fmodel = fbn.models.base.ModelWithPreprocessing(
        fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
    )

    # axis with 1D mean
    preprocessing = dict(mean=3, std=[5, 5, 5], axis=-3)
    with pytest.raises(ValueError):
        fmodel = fbn.models.base.ModelWithPreprocessing(
            fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
        )

    # axis with 1D std
    preprocessing = dict(mean=[3, 3, 3], std=5, axis=-3)
    with pytest.raises(ValueError):
        fmodel = fbn.models.base.ModelWithPreprocessing(
            fmodel._model, fmodel.bounds, fmodel.dummy, preprocessing
        )

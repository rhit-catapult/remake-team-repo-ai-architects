"""TransformerNet - the feed-forward fast-neural-style architecture."""

import re

import torch


class ConvLayer(torch.nn.Module):
    def __init__(self, in_ch, out_ch, kernel_size, stride):
        super().__init__()
        self.reflection_pad = torch.nn.ReflectionPad2d(kernel_size // 2)
        self.conv2d = torch.nn.Conv2d(in_ch, out_ch, kernel_size, stride)

    def forward(self, x):
        return self.conv2d(self.reflection_pad(x))


class ResidualBlock(torch.nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = ConvLayer(channels, channels, kernel_size=3, stride=1)
        self.in1 = torch.nn.InstanceNorm2d(channels, affine=True)
        self.conv2 = ConvLayer(channels, channels, kernel_size=3, stride=1)
        self.in2 = torch.nn.InstanceNorm2d(channels, affine=True)
        self.relu = torch.nn.ReLU()

    def forward(self, x):
        residual = x
        out = self.relu(self.in1(self.conv1(x)))
        out = self.in2(self.conv2(out))
        return out + residual


class UpsampleConvLayer(torch.nn.Module):
    def __init__(self, in_ch, out_ch, kernel_size, stride, upsample=None):
        super().__init__()
        self.upsample = upsample
        self.reflection_pad = torch.nn.ReflectionPad2d(kernel_size // 2)
        self.conv2d = torch.nn.Conv2d(in_ch, out_ch, kernel_size, stride)

    def forward(self, x):
        if self.upsample:
            x = torch.nn.functional.interpolate(x, mode="nearest", scale_factor=self.upsample)
        return self.conv2d(self.reflection_pad(x))


class TransformerNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = ConvLayer(3, 32, kernel_size=9, stride=1)
        self.in1 = torch.nn.InstanceNorm2d(32, affine=True)
        self.conv2 = ConvLayer(32, 64, kernel_size=3, stride=2)
        self.in2 = torch.nn.InstanceNorm2d(64, affine=True)
        self.conv3 = ConvLayer(64, 128, kernel_size=3, stride=2)
        self.in3 = torch.nn.InstanceNorm2d(128, affine=True)
        self.res1 = ResidualBlock(128)
        self.res2 = ResidualBlock(128)
        self.res3 = ResidualBlock(128)
        self.res4 = ResidualBlock(128)
        self.res5 = ResidualBlock(128)
        self.deconv1 = UpsampleConvLayer(128, 64, kernel_size=3, stride=1, upsample=2)
        self.in4 = torch.nn.InstanceNorm2d(64, affine=True)
        self.deconv2 = UpsampleConvLayer(64, 32, kernel_size=3, stride=1, upsample=2)
        self.in5 = torch.nn.InstanceNorm2d(32, affine=True)
        self.deconv3 = ConvLayer(32, 3, kernel_size=9, stride=1)
        self.relu = torch.nn.ReLU()

    def forward(self, x):
        y = self.relu(self.in1(self.conv1(x)))
        y = self.relu(self.in2(self.conv2(y)))
        y = self.relu(self.in3(self.conv3(y)))
        y = self.res1(y)
        y = self.res2(y)
        y = self.res3(y)
        y = self.res4(y)
        y = self.res5(y)
        y = self.relu(self.in4(self.deconv1(y)))
        y = self.relu(self.in5(self.deconv2(y)))
        return self.deconv3(y)


def load_transformer_net(path, device, dtype=torch.float32):
    """Load a pretrained TransformerNet, stripping deprecated InstanceNorm
    running stats that older saved models include."""
    model = TransformerNet()
    state = torch.load(path, map_location="cpu")
    for key in list(state.keys()):
        if re.search(r"in\d+\.running_(mean|var)$", key):
            del state[key]
    model.load_state_dict(state)
    model.to(device, dtype).eval()
    return model

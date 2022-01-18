from Dataloader.Dataloader import LoadFileParameter, SaveFileParameter, DataGenerator, DataModule, WSIQuery
import pytorch_lightning as pl
import sys
import torch
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau
import torch.nn as nn
from torchmetrics.functional import accuracy
from torchvision import datasets, models, transforms
from torch.nn.functional import softmax

class ImageClassifier(pl.LightningModule):

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.backbone = getattr(models, config["MODEL"]["Backbone"])()
        self.loss_fcn = getattr(torch.nn, self.config["MODEL"]["loss_function"])()
        self.activation = getattr(torch.nn, self.config["MODEL"]["activation"])()
        out_feats = list(backbone.children())[-1].out_features
        self.model = nn.Sequential(
            self.backbone,
            nn.Linear(out_feats, 512),
            nn.Linear(512, self.config["DATA"]["n_classes"]),
            activation,
        )

    def forward(self, x):
        return self.model(x)

    def training_step(self, train_batch, batch_idx):
        image, labels = train_batch
        image         = next(iter(image.values())) ## Take the first value in the dictonnary for single zoom
        logits        = self.forward(image)
        loss          = self.loss_fcn(logits, labels)
        preds         = torch.argmax(softmax(logits, dim=1), dim=1)
        acc           = accuracy(preds, labels)
        self.log('train_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log('train_acc', acc, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        return loss

    def validation_step(self, val_batch, batch_idx):
        image, labels = val_batch
        image         = next(iter(image.values())) ## Take the first value in the dictonnary for single zoom
        logits        = self.forward(image)
        loss          = self.loss_fcn(logits, labels)
        preds         = torch.argmax(softmax(logits, dim=1), dim=1)
        acc           = accuracy(preds, labels)
        self.log('val_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log('val_acc', acc, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        return loss

    def testing_step(self, test_batch, batch_idx):
        image, labels = test_batch
        image         = next(iter(image.values())) ## Take the first value in the dictonnary for single zoom
        logits        = self.forward(image)
        loss          = self.loss_fcn(logits, labels)
        preds         = torch.argmax(softmax(logits, dim=1), dim=1)
        acc           = accuracy(preds, labels)
        self.log('test_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log('test_acc', acc, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        return loss

    def predict_step(self, batch, batch_idx, dataloader_idx=0):
        image = batch
        image = next(iter(image.values())) ## Take the first value in the dictonnary for single zoom
        return softmax(self(image))

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(),lr=self.config["OPTIMIZER"]["lr"],eps=self.config["OPTIMIZER"]["eps"])
        #scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=self.config["OPTIMIZER"]["step_size"], gamma=self.config["OPTIMIZER"]["gamma"],verbose=True)
        return ([optimizer], [scheduler])
        #return optimizer



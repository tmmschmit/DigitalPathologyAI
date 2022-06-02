import os
from PreProcessing.PreProcessingTools import PreProcessor
import toml
from Utils import GetInfo
import pytorch_lightning as pl
from torchvision import transforms
from QA.Normalization.Colour import ColourNorm
from Model.ConvNet import ConvNet
from Dataloader.Dataloader import *


config = toml.load(sys.argv[1])

########################################################################################################################
# 1. Download all relevant files based on the configuration file

dataset = QueryFromServer(config)
Synchronize(config, dataset)
print(dataset)

########################################################################################################################
# 2. Pre-processing: create npy files

# option #1: preprocessor + save to npy
preprocessor = PreProcessor(config)
coords_file = preprocessor.getTilesFromNonBackground(dataset)
SaveFileParameter(config, coords_file)
print(coords_file)
del preprocessor

# option #2: load existing
#coords_file = LoadFileParameter(config, dataset)

########################################################################################################################
# 3. Model evaluation

name = GetInfo.format_model_name(config)

pl.seed_everything(config['ADVANCEDMODEL']['Random_Seed'], workers=True)

val_transform = transforms.Compose([
    transforms.ToTensor(),  # this also normalizes to [0,1].
    transforms.Lambda(lambda x: x * 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
    ColourNorm.Macenko(saved_fit_file=config['NORMALIZATION']['Colour_Norm_File']) if 'Colour_Norm_File' in config[
        'NORMALIZATION'] else None,
    transforms.Lambda(lambda x: x / 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


data = DataLoader(DataGenerator(coords_file, transform=val_transform, inference=True),
                  batch_size=config['BASEMODEL']['Batch_Size'],
                  num_workers=10,
                  shuffle=False,
                  pin_memory=True)

config['INTERNAL']['weights'] = torch.ones(int(config['DATA']['N_Classes'])).float()

trainer = pl.Trainer(gpus=torch.cuda.device_count(), benchmark=True, precision=config['BASEMODEL']['Precision'])
model = ConvNet.load_from_checkpoint(config=config, checkpoint_path=config['CHECKPOINT']['Model_Save_Path'])
model.eval()
predictions = trainer.predict(model, data)
predicted_classes_prob = torch.Tensor.cpu(torch.cat(predictions))

for i in range(predicted_classes_prob.shape[1]):
    coords_file['prob_' + config['DATA']['Label'] + str(i)] = pd.Series(predicted_classes_prob[:, i],
                                                                        index=coords_file.index)
    coords_file = coords_file.fillna(0)

SaveFileParameter(config, coords_file)

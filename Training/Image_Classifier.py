from Dataloader.Dataloader import *
import toml
from Utils import GetInfo
from pytorch_lightning.loggers import TensorBoardLogger
from pytorch_lightning.callbacks import ModelCheckpoint, LearningRateMonitor
import pytorch_lightning as pl
from torchvision import transforms
import torch
from QA.Normalization.Colour import ColourNorm
from Model.ConvNet import ConvNet
from sklearn import preprocessing

config = toml.load(sys.argv[1])
#config = toml.load('../Configs/sarcoma/trainer_sarcoma_convnet.ini')

########################################################################################################################
# 1. Download all relevant files based on the configuration file

dataset = QueryFromServer(config)
Synchronize(config, dataset)
print(dataset)

########################################################################################################################
# 2. Pre-processing: load existing npy files, append target label to coords_file, select tumour tiles only.

# Load pre-processed dataset. It should have been pre-processed with Inference/Preprocess.py first.
coords_file = LoadFileParameter(config, dataset)

# Mask the coords_file to only keep the tumour tiles, depending on a pre-set criteria.
coords_file = coords_file[coords_file['prob_tissue_type_tumour'] > 0.94]

# Append the target label to coords_file. 
coords_file[config['DATA']['Label']] = coords_file.apply(lambda row:dataset.loc[dataset['id_internal']==row['SVS_ID']][config['DATA']['Label']],axis=1)

config['DATA']['N_Classes'] = len(coords_file[config['DATA']['Label']].unique())
########################################################################################################################
#3 Model
# Set up logging, model checkpoint
name = GetInfo.format_model_name(config)
if 'logger_folder' in config['CHECKPOINT']:
    logger = TensorBoardLogger(os.path.join('lightning_logs', config['CHECKPOINT']['logger_folder']), name=name)
else:
    logger = TensorBoardLogger('lightning_logs', name=name)
lr_monitor = LearningRateMonitor(logging_interval='step')
checkpoint_callback = ModelCheckpoint(dirpath=config['CHECKPOINT']['Model_Save_Path'],
                                      monitor=config['CHECKPOINT']['Monitor'],
                                      filename=name + '-epoch{epoch:02d}-' + config['CHECKPOINT']['Monitor'] + '{' +
                                      config['CHECKPOINT']['Monitor'] + ':.2f}',
                                      save_top_k=1,
                                      mode=config['CHECKPOINT']['Mode'])

pl.seed_everything(config['ADVANCEDMODEL']['Random_Seed'], workers=True)

# transforms: augment data on training set
if config['AUGMENTATION']['Rand_Operations'] > 0:
    train_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Lambda(lambda x: x * 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
        ColourNorm.Macenko(saved_fit_file=config['NORMALIZATION']['Colour_Norm_File']) if 'Colour_Norm_File' in config[
            'NORMALIZATION'] else None,
        transforms.Lambda(lambda x: x / 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
        transforms.ToPILImage(),
        transforms.RandAugment(num_ops=config['AUGMENTATION']['Rand_Operations'],
                               magnitude=config['AUGMENTATION']['Rand_Magnitude']),
        # this only operates on 8-bit images (not normalised float32 tensors)
        transforms.ToTensor(),  # this also normalizes to [0,1].,
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
else:
    train_transform = transforms.Compose([
        transforms.ToTensor(),  # this also normalizes to [0,1].,
        transforms.Lambda(lambda x: x * 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
        ColourNorm.Macenko(saved_fit_file=config['NORMALIZATION']['Colour_Norm_File']) if 'Colour_Norm_File' in config[
            'NORMALIZATION'] else None,
        transforms.Lambda(lambda x: x / 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

# transforms: colour norm only on validation set
val_transform = transforms.Compose([
    transforms.ToTensor(),  # this also normalizes to [0,1].
    transforms.Lambda(lambda x: x * 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
    ColourNorm.Macenko(saved_fit_file=config['NORMALIZATION']['Colour_Norm_File']) if 'Colour_Norm_File' in config[
        'NORMALIZATION'] else None,
    transforms.Lambda(lambda x: x / 255) if 'Colour_Norm_File' in config['NORMALIZATION'] else None,
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Create LabelEncoder
le = preprocessing.LabelEncoder()
le.fit(coords_file[config['DATA']['Label']])

# Load model and train
trainer = pl.Trainer(gpus=torch.cuda.device_count(),
                     benchmark=True,
                     max_epochs=config['ADVANCEDMODEL']['Max_Epochs'],
                     precision=config['BASEMODEL']['Precision'],
                     callbacks=[checkpoint_callback, lr_monitor],
                     logger=logger)

model = ConvNet(config, label_encoder=le)

########################################################################################################################
#4 Dataloader

data = DataModule(
    coords_file,
    batch_size=config['BASEMODEL']['Batch_Size'],
    train_transform=train_transform,
    val_transform=val_transform,
    train_size=config['DATA']['Train_Size'],
    val_size=config['DATA']['Val_Size'],
    inference=False,
    dim_list=config['BASEMODEL']['Patch_Size'],
    vis_list=config['BASEMODEL']['Vis'],
    n_per_sample=config['DATA']['N_Per_Sample'],
    target=config['DATA']['Label'],
    sampling_scheme=config['DATA']['Sampling_Scheme'],
    label_encoder=le
)
GetInfo.ShowTrainValTestInfo(data, config)

config['DATA']['N_Training_Examples'] = data.train_data.__len__()
config['DATA']['loss_weights'] = torch.ones(int(config['DATA']['N_Classes'])).float()

# Give the user some insight on the data

trainer.fit(model, data)

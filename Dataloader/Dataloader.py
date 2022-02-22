import matplotlib.pyplot as plt
from pytorch_lightning import LightningDataModule, LightningModule, Trainer, seed_everything
from torch.utils.data import DataLoader
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
import numpy as np
import torch
from wsi_core.WholeSlideImage import WholeSlideImage

class DataGenerator(torch.utils.data.Dataset):

    def __init__(self, coords_file, target="tumour_label", dim_list=[(256, 256)], vis_list=[0],
                 inference=False, transform=None, target_transform=None):

        super().__init__()
        self.transform = transform
        self.target_transform = target_transform
        self.coords = coords_file
        self.vis_list = vis_list
        self.dim_list = dim_list
        self.inference = inference
        self.target = target

    def __len__(self):
        return int(self.coords.shape[0])

    def __getitem__(self, id):
        # load image
        wsi_file  = WholeSlideImage(self.coords["wsi_path"].iloc[id])

        data_dict = {}
        for dim in self.dim_list:
            for vis_level in self.vis_list:
                key = "_".join(map(str,dim))+"_"+str(vis_level)
                data_dict[key]  = np.array(wsi_file.wsi.read_region([self.coords["coords_x"].iloc[id], self.coords["coords_y"].iloc[id]],
                                                                     vis_level, dim).convert("RGB"))

        ## Transform - Data Augmentation

        if self.transform: data_dict = {key: self.transform(value) for (key, value) in data_dict.items()}
        if (self.inference): return data_dict

        else: 
            label = int(round(self.coords[self.target].iloc[id]))
            if self.target_transform:
                label = self.target_transform(label)
            return data_dict, label


class DataModule(LightningDataModule):

    def __init__(self, coords_file, train_transform=None, val_transform=None, batch_size=8, n_per_sample=5000,
                 train_size=0.7, val_size=0.3, **kwargs):
        super().__init__()
        self.batch_size = batch_size
        #coords_file = coords_file.groupby("file_id").sample(n=n_per_sample, replace=False)
        value_counts = coords_file.file_id.value_counts()
        fn_for_sampling = value_counts[value_counts > n_per_sample].index
        df1 = coords_file[coords_file['file_id'].isin(fn_for_sampling)].groupby("file_id").sample(n=n_per_sample, replace=False)

        if fn_for_sampling.shape != value_counts.shape:  # if some datasets have less than n_per_sample
            df2 = coords_file[~coords_file['file_id'].isin(fn_for_sampling)].groupby("file_id").sample(frac=1)
            coords_file = pd.concat([df1, df2])
        else:
            coords_file = df1

        svi = np.unique(coords_file.file_id)
        np.random.shuffle(svi)
        train_idx, val_idx = train_test_split(svi, test_size=val_size, train_size=train_size)
        self.train_data = DataGenerator(coords_file[coords_file.file_id.isin(train_idx)], transform=train_transform, **kwargs)
        self.val_data   = DataGenerator(coords_file[coords_file.file_id.isin(val_idx)],   transform=val_transform, **kwargs)

    def train_dataloader(self): return DataLoader(self.train_data, batch_size=self.batch_size, num_workers=10, pin_memory=True, shuffle=True)
    def val_dataloader(self):   return DataLoader(self.val_data,   batch_size=self.batch_size, num_workers=10, pin_memory=True)

def WSIQuery(config, **kwargs):  ## Select based on queries

    dataframe = pd.read_csv(config['DATA']['Mastersheet'])
    for key, item in config['CRITERIA'].items():
        dataframe = dataframe[dataframe[key].isin(item)]
    ids = dataframe['id']
    return ids

def LoadFileParameter(ids, svs_folder, patch_folder):
    coords_file = pd.DataFrame()
    for filenb, file_id in enumerate(ids):
        try:
            PatchPath = Path(patch_folder, '{}.csv'.format(file_id))
            WSIPath = Path(svs_folder, '{}.svs'.format(file_id))

            coords = pd.read_csv(PatchPath, header=0, index_col=0)
            coords = coords.astype({"coords_y": int, "coords_x": int})
            coords['file_id'] = file_id
            coords['wsi_path'] = str(WSIPath)

            if filenb == 0:
                coords_file = coords
            else:
                coords_file = coords_file.append(coords)
        except:
            print('Unable to find patch data for file {}.csv'.format(file_id))
            continue

    return coords_file


def SaveFileParameter(df, Patch_Folder, column_to_add, label_to_add):
    CoordsPath = Path(Patch_Folder)
    CoordsPath.mkdir(parents=True, exist_ok=True)
    df[label_to_add] = pd.Series(column_to_add, index=df.index)
    df = df.fillna(0)
    for file_id, df_split in df.groupby(df.file_id):
        TotalPath = Path(CoordsPath, str(file_id) + ".csv")
        df_split.to_csv(str(TotalPath))

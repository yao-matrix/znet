import csv
import glob
import os
import numpy as np
from collections import defaultdict
import candidates as ca
import image_read_write
from pandas import DataFrame as df
import pandas as pd
import candidates
import make_candidatelist_with_unet_candidates as mcwuc
import pipeline_candidates as pica
import evaluate_candidates
import operator
import evaluate_candidates

ANNOTATIONLOCATION = '../csv/annotations.csv'
MHDLOCATIONS = '../data/original_lungs/'

DO_OUTSIDE_LUNG_REMOVAL = False


def merge_pipe_and_unet(unetoutput, annotations, size):
    candidates = pd.read_csv(unetoutput)
    mergedTPCandidatesAndFPCandidates = pd.DataFrame() # a empty dataFrame
    annotation = pd.read_csv(annotations)

def save_to_csv(data_per_slice, imagename):
    dataframe = df(data_per_slice)
    dataframe.to_csv(imagename + '.csv', index = False)

def merge_candidates(csvfile, size):
    # initialize een map
    information_per_slice = defaultdict(list)
    with open(csvfile, mode = 'r') as infile:
        reader = csv.reader(infile)
        next(reader)
        for rows in reader:
            information_per_slice[rows[0]].append(map(float, rows[1:4]))
    for imagename, data_per_slice in information_per_slice.items():
        data_per_slice = remove_pipeline(data_per_slice, imagename)
        print(data_per_slice)
        data_per_slice = np.array(data_per_slice)
        if(len(data_per_slice) > 0):
            data_per_slice = candidates.merge_candidates_scan(data_per_slice, seriesuid = imagename, distance = size)
            save_to_csv(data_per_slice, imagename)


def remove_pipeline(data_per_slice, imagename):
    # print 'reading for ' + imagename
    if DO_OUTSIDE_LUNG_REMOVAL:
        lungmasklocation = MHDLOCATIONS + imagename + '.mhd'
        numpyImage, numpyOrigin, numpySpacing = image_read_write.load_itk_image(lungmasklocation)
        to_remove = []
        for coords in data_per_slice:
            voxel = ca.world_2_voxel(coords[::-1], numpyOrigin, numpySpacing)
            if((numpyImage[voxel[0]][voxel[1]][voxel[2]] != 4) and (numpyImage[voxel[0]][voxel[1]][voxel[2]] != 3)):
                to_remove.append(coords)
        for coords in to_remove:
            data_per_slice.remove(coords)
    return data_per_slice

def merge_csv(inputdirec, outputdirec, file, type):
    all_files = glob.glob(os.path.join(inputdirec, "*.csv"))
    dataf = pd.concat((pd.read_csv(f) for f in all_files))
    frame = pd.DataFrame(dataf)
    frame.to_csv(os.path.join(outputdirec, type + file + '.csv'), index = False)

def distance_lungonly_merge(parentdict, f, size):
    print('distance merging...')
    information_per_slice = defaultdict(list)
    directory = parentdict + f + 'Output'
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(parentdict + f + '.csv', mode = 'r') as infile:
        reader = csv.reader(infile)
        next(reader)
        for rows in reader:
            information_per_slice[rows[0]].append(map(float, rows[1:4]))
    for imagename, data_per_slice in information_per_slice.items():
        data_per_slice = np.array(data_per_slice)
        if (len(data_per_slice) > 0):
            data_per_slice = candidates.merge_candidates_scan(data_per_slice, seriesuid = imagename, distance = size)
            data_per_slice.to_csv(os.path.join(directory, imagename + '.csv'), index = False)
    merge_csv(directory, parentdict, f, 'merged')
    print('done')

    print('lung-only extraction...')
    directory = os.path.join(parentdict, f + 'Removed')
    if not os.path.exists(directory):
        os.makedirs(directory)
    information_per_slice = defaultdict(list)
    with open(os.path.join(parentdict, 'merged' + f + '.csv'), mode = 'r') as infile:
        reader = csv.reader(infile)
        next(reader)
        for rows in reader:
            information_per_slice[rows[0]].append(map(float, rows[1:4]))
    for imagename, data_per_slice in information_per_slice.items():
        data_per_slice = remove_pipeline(data_per_slice, imagename)
        data_per_slice = np.array(data_per_slice)
        if (len(data_per_slice) > 0):
            data_per_slice = candidates.merge_candidates_scan(data_per_slice, seriesuid = imagename, distance = 0)
            data_per_slice.to_csv(os.path.join(directory, imagename + '.csv'), index = False)
    merge_csv(directory, parentdict, f, 'removed')
    print('done')
 
    print('TPFPmerging...')
    candidates2 = pd.read_csv(os.path.join(parentdict, 'removed' + f + '.csv'))
    mergedTPCandidatesAndFPCandidates = pd.DataFrame()
    annotation = pd.read_csv(ANNOTATIONLOCATION)
    mergedTPCandidatesAndFPCandidates = mcwuc.fillTPCandidateList(candidates2, annotation, mergedTPCandidatesAndFPCandidates)
    mergedTPCandidatesAndFPCandidates.to_csv(os.path.join(parentdict, 'finalized' + f + '.csv'), columns = ['seriesuid', 'coordX', 'coordY', 'coordZ', 'label'], index = False)
    print('done')
 
    print('postfixing...')
    directory = os.path.join(parentdict, f + 'Finalized')
    if not os.path.exists(directory):
        os.makedirs(directory)
        information_per_slice = defaultdict(list)
    with open(os.path.join(parentdict, 'finalized' + f + '.csv'), mode = 'r') as infile:
        reader = csv.reader(infile)
        next(reader)
        for rows in reader:
            information_per_slice[rows[0]].append(map(float, rows[1:4]))
    for imagename, data_per_slice in information_per_slice.items():
        data_per_slice = np.array(data_per_slice)
        if (len(data_per_slice) > 0):
            data_per_slice = candidates.merge_candidates_scan(data_per_slice, seriesuid = imagename, distance = 0)
            data_per_slice.to_csv(os.path.join(directory, imagename + '.csv'), index = False)
    merge_csv(directory, parentdict, f, 'finalizedExtra')
    print('done')

    print('recall/precision calculating...')
    f2 = parentdict + 'finalizedExtra' + f + '.csv'
    candidates3 = ca.load_candidates(f2, False)
    evaluate_candidates.run(candidates3)
    print('done')

def label_csv(csvfile):
    annotated_info = defaultdict(list)
    with open(ANNOTATIONLOCATION, mode = 'r') as infile:
        reader = csv.reader(infile)
        next(reader)
        for rows in reader:
            annotated_info[rows[0]].append(map(float, rows[1:5]))

    information_per_slice = defaultdict(list)
    with open(csvfile, mode = 'r') as infile:
        reader = csv.reader(infile)
        next(reader)
        for rows in reader:
            information_per_slice[rows[0]].append(map(float, rows[1:5]))
    writer = csv.writer(f, delimiter = ',', lineterminator = '\n')
    writer.writerow(['seriesuid', 'coordX', 'coordY', 'coordZ', 'label'])
    for imagename, data_per_slice in information_per_slice.items():
        to_check = annotated_info.get(imagename)
        for coordinates in data_per_slice:
            label = 0
            if to_check is not None:
                maybe_false = evaluate_candidates.is_candidate2(coordinates[0:3], to_check)
                if(maybe_false != False):
                    coordinates[3] = 1.0
            print(imagename + ',' + str(coordinates).strip('[]').replace(' ', ''))
            data = []
            data.append(imagename)
            data.extend(coordinates)
            writer.writerow(data)
    f.close()

def froc_analyse(csvfile):
    averages = [0, 0, 0]
    FPrate = defaultdict(list)
    with open(csvfile, mode = 'r') as infile:
        reader = csv.reader(infile)
        next(reader)
        for rows in reader:
            FPrate[float(rows[0])].extend(map(float, rows[1:4]))
    for a in range(-3, 4):
        closest = min(FPrate.keys(), key = lambda x : abs(x - 2 ** a))
        averages = [x + y for x, y in zip(averages, FPrate.get(closest))]
    averages[:] = [x / 7 for x in averages]
    print(averages)


# froc_analyse('evaluation/OUTPUT/ens/froc_ensemble_bootstrapping.csv')
# froc_analyse('C:/Users/Guido/Desktop/evaluationScript/out5/froc_ensemble_bootstrapping.csv')
# label_csv('E:\uni\Medical\Project\CSVFILES\CSVFILES\AllUnet.csv')
# candidates4 = ca.load_candidates('E:\uni\Medical\Project\CSVFILES\CSVFILES\AllUnet.csv', False)
# pica.evaluate_candidates.run(candidates4)
# candidates = 'E:\uni\Medical\Project\CSVFILES\CSVFILES\candidates_unet_final_45.csv'
# annotations = 'E:/uni/Medical/Project/CSVFILES/CSVFILES/annotations.csv'
# merge_pipe_and_unet(candidates,annotations, 2)
# merge_candidates('E:\uni\Medical\Project\CSVFILES\CSVFILES\candidates_unet_final_45.csv', 2)
# distance_lungonly_merge("../data/unet_candidates_noclose3/",'candidates_unet_final_01', 2)
# distance_lungonly_merge("../data/unet_candidates_noclose3/",'candidates_unet_final_23', 2)
# distance_lungonly_merge("../data/",'candidates_unet_final_45', 2)
distance_lungonly_merge("../data/", 'candidates_unet_ALL', 2)
# distance_lungonly_merge("../data/",'candidates_unet_final_23', 2)
# distance_lungonly_merge("../data/",'candidates_unet_final_67', 2)
# distance_lungonly_merge("../data/",'candidates_unet_final_89', 2)
# distance_lungonly_merge("../data/",'candidates_unet_final_45_ALL', 2)
# distance_lungonly_merge("../data/unet_candidates_noclose3/",'candidates_unet_final_67', 2)
# distance_lungonly_merge("../data/unet_candidates_noclose3/",'candidates_unet_final_89', 2)
# merge_csv('../data/unet_final_outputs', '../data', 'AllUnet', '')

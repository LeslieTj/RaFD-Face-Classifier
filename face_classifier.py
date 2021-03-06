from __future__ import print_function, division

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
import numpy as np
import torchvision
from torchvision import datasets, models, transforms
from torch.backends import cudnn
import matplotlib.pyplot as plt
import time
import os
import copy
from  utils import imsave

device = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")

# For fast training.
cudnn.benchmark = True


def get_loader(data_dir ='/volume3/AAM-GAN/data/RaFD', mode = 'train'):

    # Data augmentation and normalization for training
    # Just normalization for validation
    data_transforms = {
        'train': transforms.Compose([
            transforms.CenterCrop(680),
            transforms.Resize(128),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.CenterCrop(680),
            transforms.Resize(128),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        
        'infer': transforms.Compose([
            transforms.Resize(128),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    }
    
    
    
    if mode == 'train':
        image_datasets = {x: datasets.ImageFolder(os.path.join(data_dir, x),
                                                  data_transforms[x])
                          for x in ['train', 'val']}
        dataloaders = {x: torch.utils.data.DataLoader(image_datasets[x], batch_size=32,
                                                     shuffle=True, num_workers=32)
                      for x in ['train', 'val']}
        dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}
        class_names = image_datasets['train'].classes
    
    else : 
    
        test_image_datasets = datasets.ImageFolder( data_dir,data_transforms['infer'])
        dataloaders = torch.utils.data.DataLoader(test_image_datasets, batch_size = 4, shuffle= False, num_workers = 4)
        dataset_sizes = len(test_image_datasets)
        class_names = test_image_datasets.classes
    
    return dataloaders, class_names, dataset_sizes
    

def visualize_save_image(data_dir = '/volume3/AAM-GAN/data/RaFD' ):


    ######### visualize the images in grid ##########
    
    dataloaders, class_names, _ = get_loader(data_dir = data_dir)
    
    # Get a batch of training data
    inputs, classes = next(iter(dataloaders['train']))
    
    # Make a grid from batch
    out = torchvision.utils.make_grid(inputs)
    imsave(out,'img.png')


def model():
    model_ft = models.resnet18(pretrained=True)
    num_ftrs = model_ft.fc.in_features    
    model_ft.fc = nn.Linear(num_ftrs, 8)
    
    return model_ft

def train_model(model, dataloaders, dataset_sizes, criterion, optimizer, scheduler, num_epochs=500):
    since = time.time()

    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0

    for epoch in range(num_epochs):
        print('Epoch {}/{}'.format(epoch, num_epochs - 1))
        print('-' * 10)

        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()  # Set model to training mode
            else:
                model.eval()   # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0

            # Iterate over data.
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward
                # track history if only in train
                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)

                    # backward + optimize only if in training phase
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                # statistics
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)
            if phase == 'train':
                scheduler.step()

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]

            print('{} Loss: {:.4f} Acc: {:.4f}'.format(
                phase, epoch_loss, epoch_acc))

            # deep copy the model
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())
                
                # save the best model
                PATH = './face_classifier.pth'
                torch.save({
                        'epoch': epoch,
                        'model_state_dict': model.state_dict(),
                        'optimizer_state_dict': optimizer.state_dict(),
                        'loss': epoch_loss,
                        'acc': epoch_acc
                        }, PATH)
                

        print()

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
    print('Best val Acc: {:4f}'.format(best_acc))

    
def evaluate_classification_err (model, checkpoint_path, dataloaders, dataset_sizes, criterion):
    
    checkpoint = torch.load(checkpoint_path)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    model.eval()
    running_loss = 0.0
    running_corrects = 0.0
    with torch.no_grad():
        for i, (inputs, labels) in enumerate(dataloaders):
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            
            loss = criterion(outputs, labels)
            # statistics
            running_loss += loss.item() * inputs.size(0)
            running_corrects += torch.sum(preds == labels.data)

        avg_loss = running_loss / dataset_sizes
        avg_acc = running_corrects.double() / dataset_sizes

            
        return avg_loss, avg_acc.item()

    
    
def visualize_model(model, dataloaders, num_images=6):
    was_training = model.training
    model.eval()
    images_so_far = 0
    fig = plt.figure()

    with torch.no_grad():
    
        for i, (inputs, labels) in enumerate(dataloaders['val']):
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)

            for j in range(inputs.size()[0]):
                images_so_far += 1
                ax = plt.subplot(num_images//2, 2, images_so_far)
                ax.axis('off')
                ax.set_title('predicted: {}'.format(class_names[preds[j]]))
                imshow(inputs.cpu().data[j])

                if images_so_far == num_images:
                    model.train(mode=was_training)
                    return
        model.train(mode=was_training)
        
        
def train(data_dir = '/volume3/AAM-GAN/data/RaFD'):
       
    
    model_ft = model()
    model_ft = model_ft.to(device)
    
    criterion = nn.CrossEntropyLoss()
    
    # Observe that all parameters are being optimized
    optimizer_ft = optim.SGD(model_ft.parameters(), lr=0.001, momentum=0.9)
    
    # Decay LR by a factor of 0.1 every 7 epochs
    exp_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=7, gamma=0.1)
    
    dataloaders, class_names, dataset_sizes = get_loader(data_dir = data_dir)
    train_model(model_ft, dataloaders, dataset_sizes, criterion, optimizer_ft, exp_lr_scheduler,
                           num_epochs=500)
   
def cls_err(data_dir='/volume3/AAM-GAN/stargan_rafd/results/output'):
    model_ft= model()
    model_ft = model_ft.to(device)
    criterion = nn.CrossEntropyLoss()
    dataloaders, class_names, dataset_sizes = get_loader(data_dir = data_dir, mode='inference')
    checkpoint = 'face_classifier.pth'
    err, acc = evaluate_classification_err(model_ft, checkpoint, dataloaders, dataset_sizes, criterion)
    print (err, acc)
 
# train the model                   
# train()

#find the classification err and accuracy
cls_err('/volume3/AAM-GAN/stargan_rafd/results/output')

    
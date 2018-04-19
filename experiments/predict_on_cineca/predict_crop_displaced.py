"""
This script predicts a dreyeve sequence with two displaced crops.
The model is trained only with central crop.
Will it generalise or learn the bias?
"""
import argparse
import os
from os.path import join

import numpy as np
import skimage.io as io
from computer_vision_utils.io_helper import read_image
from computer_vision_utils.tensor_manipulation import resize_tensor
from metrics.metrics import kld_numeric, cc_numeric
from skimage.transform import resize
from tqdm import tqdm
from train.models import DreyeveNet


def makedirs(dir_list):
    """
    Helper function to create a list of directories.

    :param dir_list: a list of directories to be created
    """

    for dir in dir_list:
        if not os.path.exists(dir):
            os.makedirs(dir)


def translate(x, pixels, side):
    assert side in ['right', 'left']

    w = x.shape[-1]

    pad = x[..., (w - pixels):] if side == 'left' else x[..., :pixels]
    pad = pad[..., ::-1]

    if side == 'left':
        xt = np.roll(x, -pixels, axis=-1)
        xt[..., (w-pixels):] = pad
    else:
        xt = np.roll(x, pixels, axis=-1)
        xt[..., :pixels] = pad

    return xt


class SequenceLoader:

    def __init__(self, sequence_dir, mean_dreyeve_image, frames_per_seq=16, h=448, w=448):

        self.sequence_dir = sequence_dir
        self.mean_dreyeve_image = mean_dreyeve_image
        self.frames_per_seq = frames_per_seq
        self.h = h
        self.w = w

        self.h_c = self.h_s = h // 4
        self.w_c = self.w_s = h // 4

        self.fr = 0  # frame counter

        self.I_ff = np.zeros(shape=(1, 3, 1, h, w), dtype='float32')
        self.I_s = np.zeros(shape=(1, 3, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.I_c = np.zeros(shape=(1, 3, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.Il_ff = np.zeros(shape=(1, 3, 1, h, w), dtype='float32')
        self.Il_s = np.zeros(shape=(1, 3, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.Il_c = np.zeros(shape=(1, 3, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.Ir_ff = np.zeros(shape=(1, 3, 1, h, w), dtype='float32')
        self.Ir_s = np.zeros(shape=(1, 3, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.Ir_c = np.zeros(shape=(1, 3, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.OF_ff = np.zeros(shape=(1, 3, 1, h, w), dtype='float32')
        self.OF_s = np.zeros(shape=(1, 3, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.OF_c = np.zeros(shape=(1, 3, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.OFl_ff = np.zeros(shape=(1, 3, 1, h, w), dtype='float32')
        self.OFl_s = np.zeros(shape=(1, 3, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.OFl_c = np.zeros(shape=(1, 3, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.OFr_ff = np.zeros(shape=(1, 3, 1, h, w), dtype='float32')
        self.OFr_s = np.zeros(shape=(1, 3, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.OFr_c = np.zeros(shape=(1, 3, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.SEG_ff = np.zeros(shape=(1, 19, 1, h, w), dtype='float32')
        self.SEG_s = np.zeros(shape=(1, 19, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.SEG_c = np.zeros(shape=(1, 19, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.SEGl_ff = np.zeros(shape=(1, 19, 1, h, w), dtype='float32')
        self.SEGl_s = np.zeros(shape=(1, 19, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.SEGl_c = np.zeros(shape=(1, 19, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.SEGr_ff = np.zeros(shape=(1, 19, 1, h, w), dtype='float32')
        self.SEGr_s = np.zeros(shape=(1, 19, frames_per_seq, self.h_s, self.w_s), dtype='float32')
        self.SEGr_c = np.zeros(shape=(1, 19, frames_per_seq, self.h_c, self.w_c), dtype='float32')

        self.Y_sal = np.zeros(shape=(1, 1, self.h, self.w), dtype='float32')
        self.Y_fix = np.zeros(shape=(1, 1, self.h, self.w), dtype='float32')

        self.Yl_sal = np.zeros(shape=(1, 1, self.h, self.w), dtype='float32')
        self.Yl_fix = np.zeros(shape=(1, 1, self.h, self.w), dtype='float32')

        self.Yr_sal = np.zeros(shape=(1, 1, self.h, self.w), dtype='float32')
        self.Yr_fix = np.zeros(shape=(1, 1, self.h, self.w), dtype='float32')

        self.load_first()

    def load_first(self):

        for fr in xrange(0, self.frames_per_seq):

            self.fr = fr

            # read image
            x = read_image(join(self.sequence_dir, 'frames', '{:06d}.jpg'.format(fr)), channels_first=True) \
                - self.mean_dreyeve_image
            xl = translate(x, pixels=500, side='left')
            xr = translate(x, pixels=500, side='right')
            self.I_s[0, :, fr, :, :] = resize_tensor(x, new_size=(self.h_s, self.w_s))
            self.Il_s[0, :, fr, :, :] = resize_tensor(xl, new_size=(self.h_s, self.w_s))
            self.Ir_s[0, :, fr, :, :] = resize_tensor(xr, new_size=(self.h_s, self.w_s))

            # read of
            of = read_image(join(self.sequence_dir, 'optical_flow', '{:06d}.png'.format(fr + 1)),
                            channels_first=True, resize_dim=(h, w))
            of -= np.mean(of, axis=(1, 2), keepdims=True)  # remove mean
            ofl = translate(of, pixels=500, side='left')
            ofr = translate(of, pixels=500, side='right')
            self.OF_s[0, :, fr, :, :] = resize_tensor(of, new_size=(self.h_s, self.w_s))
            self.OFl_s[0, :, fr, :, :] = resize_tensor(ofl, new_size=(self.h_s, self.w_s))
            self.OFr_s[0, :, fr, :, :] = resize_tensor(ofr, new_size=(self.h_s, self.w_s))

            # read semseg
            seg = resize_tensor(np.load(join(self.sequence_dir, 'semseg', '{:06d}.npz'.format(fr)))['arr_0'][0],
                                new_size=(h, w))
            segl = translate(seg, pixels=500, side='left')
            segr = translate(seg, pixels=500, side='right')

            self.SEG_s[0, :, fr, :, :] = resize_tensor(seg, new_size=(self.h_s, self.w_s))
            self.SEGl_s[0, :, fr, :, :] = resize_tensor(segl, new_size=(self.h_s, self.w_s))
            self.SEGr_s[0, :, fr, :, :] = resize_tensor(segr, new_size=(self.h_s, self.w_s))

        self.I_ff[0, :, 0, :, :] = resize_tensor(x, new_size=(self.h, self.w))
        self.Il_ff[0, :, 0, :, :] = resize_tensor(xl, new_size=(self.h, self.w))
        self.Ir_ff[0, :, 0, :, :] = resize_tensor(xr, new_size=(self.h, self.w))

        self.OF_ff[0, :, 0, :, :] = resize_tensor(of, new_size=(self.h, self.w))
        self.OFl_ff[0, :, 0, :, :] = resize_tensor(ofl, new_size=(self.h, self.w))
        self.OFr_ff[0, :, 0, :, :] = resize_tensor(ofr, new_size=(self.h, self.w))

        self.SEG_ff[0, :, 0, :, :] = resize_tensor(seg, new_size=(self.h, self.w))
        self.SEGl_ff[0, :, 0, :, :] = resize_tensor(segl, new_size=(self.h, self.w))
        self.SEGr_ff[0, :, 0, :, :] = resize_tensor(segr, new_size=(self.h, self.w))

        y_sal = read_image(join(self.sequence_dir, 'saliency', '{:06d}.png'.format(fr)), channels_first=False,
                           color=False)
        yl_sal = translate(y_sal, pixels=500, side='left')
        yr_sal = translate(y_sal, pixels=500, side='right')
        self.Y_sal[0, 0] = resize_tensor(y_sal[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yl_sal[0, 0] = resize_tensor(yl_sal[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yr_sal[0, 0] = resize_tensor(yr_sal[np.newaxis, ...], new_size=(self.h, self.w))[0]

        y_fix = read_image(join(self.sequence_dir, 'saliency_fix', '{:06d}.png'.format(fr)), channels_first=False,
                           color=False)
        yl_fix = translate(y_fix, pixels=500, side='left')
        yr_fix = translate(y_fix, pixels=500, side='right')
        self.Y_fix[0, 0] = resize_tensor(y_fix[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yl_fix[0, 0] = resize_tensor(yl_fix[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yr_fix[0, 0] = resize_tensor(yr_fix[np.newaxis, ...], new_size=(self.h, self.w))[0]

    def get(self):

        X = [x.copy() for x in [self.I_ff, self.I_s, self.I_c, self.OF_ff, self.OF_s, self.OF_c, self.SEG_ff, self.SEG_s, self.SEG_c]]
        Xl = [x.copy() for x in [self.Il_ff, self.Il_s, self.Il_c, self.OFl_ff, self.OFl_s, self.OFl_c, self.SEGl_ff, self.SEGl_s, self.SEGl_c]]
        Xr = [x.copy() for x in [self.Ir_ff, self.Ir_s, self.Ir_c, self.OFr_ff, self.OFr_s, self.OFr_c, self.SEGr_ff, self.SEGr_s, self.SEGr_c]]
        GT = [x.copy() for x in [self.Y_sal, self.Y_fix]]
        GTl = [x.copy() for x in [self.Yl_sal, self.Yl_fix]]
        GTr = [x.copy() for x in [self.Yr_sal, self.Yr_fix]]

        return X, Xl, Xr, GT, GTl, GTr

    def roll(self):

        self.fr += 1

        self.I_s, self.I_c, self.OF_s, self.OF_c, self.SEG_s, self.SEG_c, \
        self.Il_s, self.Il_c, self.OFl_s, self.OFl_c, self.SEGl_s, self.SEGl_c, \
        self.Ir_s, self.Ir_c, self.OFr_s, self.OFr_c, self.SEGr_s, self.SEGr_c = [
            np.roll(x, -1, axis=2) for x in
            [self.I_s, self.I_c, self.OF_s, self.OF_c, self.SEG_s, self.SEG_c,
            self.Il_s, self.Il_c, self.OFl_s, self.OFl_c, self.SEGl_s, self.SEGl_c,
            self.Ir_s, self.Ir_c, self.OFr_s, self.OFr_c, self.SEGr_s, self.SEGr_c]]

        # read image
        x = read_image(join(self.sequence_dir, 'frames', '{:06d}.jpg'.format(self.fr)), channels_first=True) \
            - self.mean_dreyeve_image
        xl = translate(x, pixels=500, side='left')
        xr = translate(x, pixels=500, side='right')
        self.I_s[0, :, -1, :, :] = resize_tensor(x, new_size=(self.h_s, self.w_s))
        self.Il_s[0, :, -1, :, :] = resize_tensor(xl, new_size=(self.h_s, self.w_s))
        self.Ir_s[0, :, -1, :, :] = resize_tensor(xr, new_size=(self.h_s, self.w_s))

        # read of
        of = read_image(join(self.sequence_dir, 'optical_flow', '{:06d}.png'.format(self.fr + 1)),
                        channels_first=True, resize_dim=(h, w))
        of -= np.mean(of, axis=(1, 2), keepdims=True)  # remove mean
        ofl = translate(of, pixels=500, side='left')
        ofr = translate(of, pixels=500, side='right')
        self.OF_s[0, :, -1, :, :] = resize_tensor(of, new_size=(self.h_s, self.w_s))
        self.OFl_s[0, :, -1, :, :] = resize_tensor(ofl, new_size=(self.h_s, self.w_s))
        self.OFr_s[0, :, -1, :, :] = resize_tensor(ofr, new_size=(self.h_s, self.w_s))

        # read semseg
        seg = resize_tensor(np.load(join(self.sequence_dir, 'semseg', '{:06d}.npz'.format(self.fr)))['arr_0'][0],
                            new_size=(h, w))
        segl = translate(seg, pixels=500, side='left')
        segr = translate(seg, pixels=500, side='right')

        self.SEG_s[0, :, -1, :, :] = resize_tensor(seg, new_size=(self.h_s, self.w_s))
        self.SEGl_s[0, :, -1, :, :] = resize_tensor(segl, new_size=(self.h_s, self.w_s))
        self.SEGr_s[0, :, -1, :, :] = resize_tensor(segr, new_size=(self.h_s, self.w_s))

        self.I_ff[0, :, 0, :, :] = resize_tensor(x, new_size=(self.h, self.w))
        self.Il_ff[0, :, 0, :, :] = resize_tensor(xl, new_size=(self.h, self.w))
        self.Ir_ff[0, :, 0, :, :] = resize_tensor(xr, new_size=(self.h, self.w))

        self.OF_ff[0, :, 0, :, :] = resize_tensor(of, new_size=(self.h, self.w))
        self.OFl_ff[0, :, 0, :, :] = resize_tensor(ofl, new_size=(self.h, self.w))
        self.OFr_ff[0, :, 0, :, :] = resize_tensor(ofr, new_size=(self.h, self.w))

        self.SEG_ff[0, :, 0, :, :] = resize_tensor(seg, new_size=(self.h, self.w))
        self.SEGl_ff[0, :, 0, :, :] = resize_tensor(segl, new_size=(self.h, self.w))
        self.SEGr_ff[0, :, 0, :, :] = resize_tensor(segr, new_size=(self.h, self.w))

        y_sal = read_image(join(self.sequence_dir, 'saliency', '{:06d}.png'.format(self.fr)), channels_first=False,
                           color=False)
        yl_sal = translate(y_sal, pixels=500, side='left')
        yr_sal = translate(y_sal, pixels=500, side='right')
        self.Y_sal[0, 0] = resize_tensor(y_sal[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yl_sal[0, 0] = resize_tensor(yl_sal[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yr_sal[0, 0] = resize_tensor(yr_sal[np.newaxis, ...], new_size=(self.h, self.w))[0]

        y_fix = read_image(join(self.sequence_dir, 'saliency_fix', '{:06d}.png'.format(self.fr)), channels_first=False,
                           color=False)
        yl_fix = translate(y_fix, pixels=500, side='left')
        yr_fix = translate(y_fix, pixels=500, side='right')
        self.Y_fix[0, 0] = resize_tensor(y_fix[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yl_fix[0, 0] = resize_tensor(yl_fix[np.newaxis, ...], new_size=(self.h, self.w))[0]
        self.Yr_fix[0, 0] = resize_tensor(yr_fix[np.newaxis, ...], new_size=(self.h, self.w))[0]



import matplotlib.cm as cm
cm = cm.get_cmap('jet')


def save_blendmaps(path, tensors):
    X, Xl, Xr, Y, Yl, Yr, GT, GTl, GTr = map(np.squeeze, tensors)

    X, Xl, Xr = (X - np.min(X)), (Xl - np.min(Xl)), (Xr - np.min(Xr))
    X, Xl, Xr = (X / np.max(X)), (Xl / np.max(Xl)), (Xr / np.max(Xr))
    X, Xl, Xr = X.transpose(1, 2, 0), Xl.transpose(1, 2, 0), Xr.transpose(1, 2, 0)

    Y, Yl, Yr = (Y - np.min(Y)), (Yl - np.min(Yl)), (Yr - np.min(Yr))
    Y, Yl, Yr = (Y / np.max(Y)), (Yl / np.max(Yl)), (Yr / np.max(Yr))
    Y, Yl, Yr = map(cm, (Y, Yl, Yr))

    GT, GTl, GTr = (GT - np.min(GT)), (GTl - np.min(GTl)), (GTr - np.min(GTr))
    GT, GTl, GTr = (GT / np.max(GT)), (GTl / np.max(GTl)), (GTr / np.max(GTr))
    GT, GTl, GTr = map(cm, (GT, GTl, GTr))

    img_pred = np.concatenate((0.5 * Xl + 0.5 * Yl[:, :, :3],
                               0.5 * X + 0.5 * Y[:, :, :3],
                               0.5 * Xr + 0.5 * Yr[:, :, :3])
                              , axis=0)
    img_gt = np.concatenate((0.5 * Xl + 0.5 * GTl[:, :, :3],
                             0.5 * X + 0.5 * GT[:, :, :3],
                             0.5 * Xr + 0.5 * GTr[:, :, :3])
                            , axis=0)

    img = np.concatenate((img_pred, img_gt), axis=1)
    img = resize(img, (448 * 3, 448 * 4))

    io.imsave(path, img)


if __name__ == '__main__':

    frames_per_seq, h, w = 16, 448, 448
    verbose = True

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--seq")
    parser.add_argument("--pred_dir")
    args = parser.parse_args()

    assert args.seq is not None, 'Please provide a correct dreyeve sequence'
    assert args.pred_dir is not None, 'Please provide a correct pred_dir'

    dreyeve_dir = '/majinbu/public/DREYEVE/DATA'  # local

    # load mean dreyeve image
    mean_dreyeve_image = read_image(join(dreyeve_dir, 'dreyeve_mean_frame.png'), channels_first=True)

    # get the models
    dreyevenet_model = DreyeveNet(frames_per_seq=frames_per_seq, h=h, w=w)
    dreyevenet_model.compile(optimizer='adam', loss='kld')  # do we need this?
    dreyevenet_model.load_weights('dreyevenet_model_central_crop.h5')  # load weights

    # set up pred directory
    image_pred_dir = join(args.pred_dir, '{:02d}'.format(int(args.seq)), 'blend')
    makedirs([image_pred_dir])

    sequence_dir = join(dreyeve_dir, '{:02d}'.format(int(args.seq)))

    # set up sequence loader
    loader = SequenceLoader(sequence_dir, mean_dreyeve_image)

    for sample in tqdm(range(15, 7500 - 1)):

        X, Xl, Xr, GT, GTl, GTr = loader.get()
        loader.roll()

        GT_sal, GT_fix = GT
        GTl_sal, GTl_fix = GTl
        GTr_sal, GTr_fix = GTr

        Y = dreyevenet_model.predict(X)[0]
        Yl = dreyevenet_model.predict(Xl)[0]
        Yr = dreyevenet_model.predict(Xr)[0]

        # save model output
        save_blendmaps(join(image_pred_dir, '{:06d}.jpeg'.format(sample)),
                       (X[0], Xl[0], Xr[0], Y, Yl, Yr, GT_fix, GTl_fix, GTr_fix))

        # save some metrics
        with open(join(args.pred_dir, '{:02d}'.format(int(args.seq)), 'kld.txt'), 'a') as metric_file:
            metric_file.write('{},{},{},{},{}\n'.format(sample,
                                                        kld_numeric(GT_sal, Y),
                                                        kld_numeric(GT_fix, Y),
                                                        kld_numeric(GTl_sal, Yl),
                                                        kld_numeric(GTl_fix, Yl),
                                                        kld_numeric(GTr_sal, Yr),
                                                        kld_numeric(GTr_fix, Yr)
                                                        ))
        with open(join(args.pred_dir, '{:02d}'.format(int(args.seq)), 'cc.txt'), 'a') as metric_file:
            metric_file.write('{},{},{},{},{}\n'.format(sample,
                                                        cc_numeric(GT_sal, Y),
                                                        cc_numeric(GT_fix, Y),
                                                        cc_numeric(GTl_sal, Yl),
                                                        cc_numeric(GTl_fix, Yl),
                                                        cc_numeric(GTr_sal, Yr),
                                                        cc_numeric(GTr_fix, Yr)
                                                        ))

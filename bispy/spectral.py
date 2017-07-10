#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This file is part of BiSPy.
This program contains several classes to perform spectral analysis of bivariate
signals.
"""
# import modules and packages
import numpy as np
import quaternion
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # required for 3D plot
import matplotlib.gridspec as gridspec

from spectrum import dpss

from . import qfft
from . import utils


class Periodogram(object):
    '''
    Compute the periodogram of bivariate
    signals taken as (1, i)-quaternion valued signals.

    Parameters
    ----------
    t : array_type
        time samples array

    x : array_type
        input signal array (has to be of quaternion dtype)

    compute : bool, optional
        Flag activating computation of the estimate. Default is true. If False
        one has to run the compute() method manually.

    Attributes
    ----------
    t : array_type
        time samples array

    signal : array_type
        input signal array

    f : array_type
        sampled frequencies array

    density : array_type
        spectral density quaternion array

    S0, S1, S2, S3 : array_type
       Stokes parameters, non-normalized [w.r.t. S0]

    S1n, S2n, S3n : array_type
        normalized Stokes parameters [w.r.t. S0] using the
        tolerance factor `tol`. They are not computed by
        default. See `normalize`.

    Phi : array_type
        Degree of polarization. Not computed by default; See `normalize`.

    '''

    def __init__(self, t, x, computeFlag=True):

        if x.dtype != 'quaternion':
            raise ValueError('signal array should be of quaternion type.')

        # Store the signal and parameters
        self.t = t
        self.signal = x

        N = np.size(x, 0)
        dt = (t[1] - t[0])
        self.f = np.fft.fftfreq(N) / dt

        self.density = np.zeros(N, dtype='quaternion')

        if computeFlag is True:
            self.compute()

        # and SO, S1, S2, S3 associated

        self.S0, self.S1, self.S2, self.S3 = self._getStokes()

        # initialize normalized Stokes and degree of polarization
        self.S1n = np.zeros_like(self.S0)
        self.S2n = np.zeros_like(self.S0)
        self.S3n = np.zeros_like(self.S0)

        self.Phi = np.zeros_like(self.S0)

    def compute(self):
        ''' Low-level function. Compute Periodogram estimate'''
        # compute the QFT of x
        dt = (self.t[1] - self.t[0])
        N = np.size(self.signal, 0)

        QFTx = qfft.Qfft(self.signal)

        # then the spectral density Gamma_{xx}

        self.density = dt / N * (np.norm(QFTx) + utils.StokesNorm(QFTx) *
                quaternion.y)


    def __add__(self, other):
        if np.any(self.t != other.t) is True:
            raise ValueError('Cannot sum Periodograms with differents time \
                arrays')

        new = Periodogram(self.t, self.signal, computeFlag=False)  # keep self data

        # update density
        new.density = self.density + other.density

        # and SO, S1, S2, S3 associated
        new.S0, new.S1, new.S2, new.S3 = new._getStokes()

        return new

    def __mul__(self, scalar):
        if np.size(scalar) > 1:
            raise ValueError('Only scalar multiplication is supported')

        new = Periodogram(self.t, self.signal, computeFlag=False)  # keep self data

        # update density
        new.density = scalar * self.density

        # and SO, S1, S2, S3 associated
        new.S0, new.S1, new.S2, new.S3 = new._getStokes()

        return new

    def __rmul__(self, scalar):
        return self * scalar

    def _getStokes(self):
        '''Low-level function.
        Extract extract Stokes parameters from the spectral density
        \Gamma_{xx}.
        Recall that

            \Gamma_{xx} = S0 + iS_3 + jS_1 + kS_2

        Returns
        -------
        S0, S1, S2, S2: array_type
            Stokes parameters
        '''
        g1, g2 = utils.sympSplit(self.density)

        S0 = g1.real
        S1 = g1.imag
        S3 = g2.real
        S2 = g2.imag

        return S0, S1, S2, S3

    def normalize(self, tol=0.0):

        ''' Normalize Stokes parameters wrt S0.
        In addition, compute the degree of polarization Phi.

        Parameters
        ----------
        tol : float, optional
            tolerance factor used in Stokes parameters normalization.
            Default is 0.0

        Returns
        -------
        self.S1n, self.S2n, self.S3n : array_type
            normalized Stokes parameters

        self.Phi : array_type
            degree of polarization

        See also
        --------
        utils.normalizeStokes
        '''

        self.S1n, self.S2n, self.S3n = utils.normalizeStokes(self.S0, self.S1,
            self.S2, self.S3, tol=tol)

        self.Phi = np.sqrt(self.S1n**2 + self.S2n**2 + self.S3n**2)

    def plot(self):
        '''Generic plot of spectral estimates'''

        fig, axes = _plotResultSpectral(self.t, self.signal, self)
        fig.show()
        return fig, axes


class Multitaper(object):
    '''
    Compute a multitaper spectral estimate of the spectrum of bivariate
    signals taken as (1, i)-quaternion valued signals.
    The data tapers are chosen as discrete-prolate spheroidal sequences
    (dpss or Slepian tapers). This class requires the `spectrum` package for dpss calculations.

    Parameters
    ----------
    t : array_type
        time samples array

    x : array_type
        input signal array (has to be of quaternion dtype)

    bw : float, optional
        spectral bandwidth. Default is 2.5

    computeFlag : bool, optional
        Flag activating computation of the estimate. Default is true. If False
        one has to run the compute() method manually.

    Attributes
    ----------
    t : array_type
        time samples array

    signal : array_type
        input signal array

    f : array_type
        sampled frequencies array

    densities : array_type
        spectral density quaternion array for each taper

    density : array_type
        spectral density quaternion array

    dpss : array_type
        data tapers used

    S0, S1, S2, S3 : array_type
       Stokes parameters, non-normalized [w.r.t. S0]

    S1n, S2n, S3n : array_type
        normalized Stokes parameters [w.r.t. S0] using the
        tolerance factor `tol`. They are not computed by
        default. See `normalize`.

    Phi : array_type
        Degree of polarization. Not computed by default; See `normalize`.

    '''

    def __init__(self, t, x, bw=2.5, computeFlag=True):

        if x.dtype != 'quaternion':
            raise ValueError('signal array should be of quaternion type.')

        # Store the signal and parameters
        self.t = t
        self.signal = x

        N = np.size(x, 0)
        dt = (t[1] - t[0])
        self.f = np.fft.fftfreq(N) / dt

        # compute number of tapers
        Nmt = int(np.floor(2 * bw)) - 1  # add reference here

        # define multitaper array

        self.densities = np.zeros((N, Nmt), dtype='quaternion')
        self.dpss = np.zeros((N, Nmt))

        if computeFlag is True:
             self.compute(bw=bw)

        # simple average (workaround needed since quaternion arrays cannot be
        # averaged simply)
        self.density = quaternion.as_quat_array(np.mean(quaternion.as_float_array(self.densities), axis=1))

        # and SO, S1, S2, S3 associated
        self.S0, self.S1, self.S2, self.S3 = self._getStokes()

        # initialize normalized Stokes and degree of polarization
        self.S1n = np.zeros_like(self.S0)
        self.S2n = np.zeros_like(self.S0)
        self.S3n = np.zeros_like(self.S0)

        self.Phi = np.zeros_like(self.S0)

    def compute(self, bw=2.5):

        ''' Low-level method that computes the multitaper estimate
        '''
        N = np.size(self.dpss, 0)
        Nmt = np.size(self.dpss, 1)
        dt = (self.t[1] - self.t[0])
        # data tapers
        print('Number of data tapers: ' + str(Nmt))
        [self.dpss, eigens] = dpss(N, bw, Nmt)

        # compute Nmt tapered periodograms
        for n in range(Nmt):

            QFTx = qfft.Qfft(self.signal * self.dpss[:, n])  # tapered QFT

            self.densities[:, n] = dt * (np.norm(QFTx) +
                utils.StokesNorm(QFTx) * quaternion.y)

    def __add__(self, other):
        if np.any(self.t != other.t) is True:
            raise ValueError('Cannot sum Periodograms with differents time \
                arrays')

        new = Multitaper(self.t, self.signal, computeFlag=False)  # keep self data

        # update density
        new.density = self.density + other.density

        # and SO, S1, S2, S3 associated
        new.S0, new.S1, new.S2, new.S3 = new._getStokes()

        return new

    def __mul__(self, scalar):
        if np.size(scalar) > 1:
            raise ValueError('Only scalar multiplication is supported')

        new = Multitaper(self.t, self.signal, computeFlag=False)  # keep self data

        # update density
        new.density = scalar * self.density

        # and SO, S1, S2, S3 associated
        new.S0, new.S1, new.S2, new.S3 = new._getStokes()

        return new

    def __rmul__(self, scalar):
        return self * scalar

    def _getStokes(self):
        '''Low-level function.
        Extract extract Stokes parameters from the spectral density
        \Gamma_{xx}.
        Recall that

            \Gamma_{xx} = S0 + iS_3 + jS_1 + kS_2

        Returns
        -------
        S0, S1, S2, S2: array_type
            Stokes parameters
        '''
        g1, g2 = utils.sympSplit(self.density)

        S0 = g1.real
        S1 = g1.imag
        S3 = g2.real
        S2 = g2.imag

        return S0, S1, S2, S3

    def normalize(self, tol=0.0):

        ''' Normalize Stokes parameters wrt S0.
        In addition, compute the degree of polarization Phi.

        Parameters
        ----------
        tol : float, optional
            tolerance factor used in Stokes parameters normalization.
            Default is 0.0

        Returns
        -------
        self.S1n, self.S2n, self.S3n : array_type
            normalized Stokes parameters

        self.Phi : array_type
            degree of polarization

        See also
        --------
        utils.normalizeStokes
        '''

        self.S1n, self.S2n, self.S3n = utils.normalizeStokes(self.S0, self.S1,
            self.S2, self.S3, tol=tol)

        self.Phi = np.sqrt(self.S1n**2 + self.S2n**2 + self.S3n**2)

    def plot(self):
        '''Generic plot of spectral estimates'''

        fig, axes = _plotResultSpectral(self.t, self.signal, self)
        fig.show()
        return fig, axes


def _plotResultSpectral(t, sig, spe):

    N = np.size(t)

    fig = plt.figure(figsize=(12, 8))
    gs = gridspec.GridSpec(4, 2)
    gs.update(left=0.0, right=0.98, hspace=0, wspace=0.05)

    # axes
    ax_sig = plt.subplot(gs[0:3, 0], projection='3d')

    gs1 = gridspec.GridSpec(4, 2)
    gs1.update(left=0.05, right=0.92, hspace=0.0)
    ax_S0 = plt.subplot(gs1[3:4, 0])

    gs2 = gridspec.GridSpec(4, 2)
    gs2.update(left=0.1, right=0.98, hspace=0)

    ax_s1 = plt.subplot(gs2[0, 1])
    ax_s2 = plt.subplot(gs2[1, 1])
    ax_s3 = plt.subplot(gs2[2, 1])

    gs3 = gridspec.GridSpec(4, 2)
    gs3.update(left=0.1, right=0.98, hspace=0.2)
    ax_phi = plt.subplot(gs3[3, 1])

    #########################################################
    #ax_sig
    if sig.dtype == 'quaternion':
        x1, x2 = utils.sympSplit(sig)
        x = x1.real + 1j * x2.real
    else: 
        x = sig

    ax_sig.plot(t, np.real(x), np.imag(x), color='k')

    tmin = ax_sig.get_xlim3d()[0]
    tmax = ax_sig.get_xlim3d()[1]
    xmin = min(ax_sig.get_ylim3d()[0], ax_sig.get_zlim3d()[0])
    xmax = max(ax_sig.get_ylim3d()[1], ax_sig.get_zlim3d()[1])
    ymin = min(ax_sig.get_ylim3d()[0], ax_sig.get_zlim3d()[0])
    ymax = max(ax_sig.get_ylim3d()[1], ax_sig.get_zlim3d()[1])

    # surfaces

    # complex plane
    xx_c, yy_c = np.meshgrid(np.linspace(xmin, xmax), np.linspace(ymin, ymax))
    ax_sig.plot_surface(-.05*(tmin+tmax), xx_c, yy_c,  alpha=0.05, color='gray', rstride = 100, cstride=100)
    ax_sig.plot(x.real, x.imag, -.05*(tmin+tmax), zdir='x', color='gray')
    ax_sig.set_xlim([-.05*(tmin+tmax), tmax])

    # real proj
    xx_r, yy_r = np.meshgrid(np.linspace(tmin, tmax), np.linspace(xmin, xmax))
    ax_sig.plot_surface(xx_r, yy_r, 1.05*ymin, alpha=0.05, color='gray', rstride = 100, cstride=100)
    ax_sig.plot(t, x.real, ymin*1.05, zdir='z', color='gray')
    ax_sig.set_zlim([1.05*ymin, ymax])

    #imaginary proj
    xx_i, yy_i = np.meshgrid(np.linspace(tmin, tmax), np.linspace(ymin, ymax))
    ax_sig.plot_surface(xx_i, 1.05*xmax, yy_i,  alpha=0.05, color='gray',rstride = 100, cstride=100)
    ax_sig.plot(t, x.imag, 1.05*xmax, zdir='y', color='gray')
    ax_sig.set_ylim([xmin, 1.05*xmax])

    # replot to avoid 'overlays'
    ax_sig.plot(t, np.real(x), np.imag(x), color='k')
    proj3d.persp_transformation = _orthogonal_proj
    #########################################################
    # ax_S0
    end = N // 2 - 1
    line_per, = ax_S0.semilogy(spe.f[:end], spe.S0[:end], color='k')

    ax_S0.set_xlim([spe.f[0], spe.f[N // 2 -1]])

    boundsS0min = np.min(spe.S0)
    boundsS0max = np.max(spe.S0)

    logBoundsmin = np.floor(np.log10(boundsS0min))
    logBoundsmax = np.ceil(np.log10(boundsS0max))

    ax_S0.spines['left'].set_bounds(0.6*10**(logBoundsmin), 1.4*10**(logBoundsmax))

    # Hide the right and top spines
    ax_S0.spines['right'].set_visible(False)
    ax_S0.spines['top'].set_visible(False)
    ax_S0.yaxis.set_ticks_position('left')
    ax_S0.xaxis.set_ticks_position('bottom')

    ax_S0.set_ylim((0.2*10**(logBoundsmin), 1.2*10**(logBoundsmax)))
    ax_S0.set_yticks(np.logspace(logBoundsmin, logBoundsmax, 1 + logBoundsmax-logBoundsmin))
    ax_S0.minorticks_off()
    #labels
    ax_S0.set_ylabel(r'$S_0(\nu)$')
    ax_S0.set_xlabel('Frequency '+ r'$\nu$' + ' [Hz]')

    #ax_s1
    ax_s1.axhline(0, color='gray', lw='1')
    ax_s1.plot(spe.f[:end], spe.S1n[:end], color='black', lw='2')

    ax_s1.set_xlim([spe.f[0], spe.f[N // 2-1]])
    ax_s1.set_xticks([])
    ax_s1.set_ylim((-1.2, 1.2))
    ax_s1.set_yticks([-1, 0, 1])
    # Only draw spine between the y-ticks
    ax_s1.spines['left'].set_bounds(-1.1, 1.1)
    # Hide the right and top spines
    ax_s1.spines['right'].set_visible(False)
    ax_s1.spines['top'].set_visible(False)
    ax_s1.spines['bottom'].set_visible(False)
    ax_s1.yaxis.set_ticks_position('left')
    ax_s1.xaxis.set_ticks_position('bottom')
    #labels
    ax_s1.set_ylabel(r'$s_1(\nu)$')

    #ax_s2
    ax_s2.axhline(0, color='gray', lw='1')
    ax_s2.plot(spe.f[:end], spe.S2n[:end], color='black', lw='2')

    ax_s2.set_xlim([spe.f[0], spe.f[N // 2 - 1]])
    ax_s2.set_xticks([])
    ax_s2.set_ylim((-1.2, 1.2))
    ax_s2.set_yticks([-1, 0, 1])
    # Only draw spine between the y-ticks
    ax_s2.spines['left'].set_bounds(-1.1, 1.1)
    # Hide the right and top spines
    ax_s2.spines['right'].set_visible(False)
    ax_s2.spines['top'].set_visible(False)
    ax_s2.spines['bottom'].set_visible(False)
    ax_s2.yaxis.set_ticks_position('left')
    ax_s2.xaxis.set_ticks_position('bottom')
    #labels
    ax_s2.set_ylabel(r'$s_2(\nu)$')

    #ax_s3
    ax_s3.axhline(0, color='gray', lw='1')

    ax_s3.plot(spe.f[:end], spe.S3n[:end], color='black', lw='2')

    ax_s3.set_xlim([spe.f[0], spe.f[N // 2 - 1]])

    ax_s3.set_ylim((-1.2, 1.2))
    ax_s3.set_yticks([-1, 0, 1])
    # Only draw spine between the y-ticks
    ax_s3.spines['left'].set_bounds(-1.1, 1.1)
    # Hide the right and top spines
    ax_s3.spines['right'].set_visible(False)
    ax_s3.spines['top'].set_visible(False)
    ax_s3.spines['bottom'].set_visible(False)
    ax_s3.yaxis.set_ticks_position('left')
    ax_s3.xaxis.set_ticks_position('bottom')
    # Only show ticks on the left and bottom spines
    ax_s3.set_ylim((-1.6, 1.2))
   # ax_s3.set_xticks([0, N/4, N/2])
    ax_s3.spines['bottom'].set_visible(True)
    ax_s3.yaxis.set_ticks_position('left')
    ax_s3.xaxis.set_ticks_position('bottom')
    #labels
    ax_s3.set_ylabel(r'$s_3(\nu)$')
    #ax_s3.set_xlabel('Frequency '+ r'$\nu$')
    #ax_phi
    ax_phi.plot(spe.f[:end], spe.Phi[:end], color='black', lw='2')

    ax_phi.set_xlim([spe.f[0], spe.f[N // 2 - 1]])
    ax_phi.set_yticks([0, 1])
    # Only draw spine between the y-ticks
    ax_phi.spines['left'].set_bounds(-0.1, 1.1)
    # Hide the right and top spines
    ax_phi.spines['right'].set_visible(False)
    ax_phi.spines['top'].set_visible(False)
    ax_phi.yaxis.set_ticks_position('left')
    ax_phi.xaxis.set_ticks_position('bottom')
    # Only show ticks on the left and bottom spines
    ax_phi.set_ylim((-.2, 1.5))
    #ax_phi.set_xticks([0, N/4, N/2])
    #labels
    ax_phi.set_ylabel(r'$\Phi(\nu)$')
    ax_phi.set_xlabel('Frequency '+ r'$\nu$'+ ' [Hz]')

    axes = [ax_sig, ax_S0, ax_s1, ax_s2, ax_s3, ax_phi]
    return fig, axes

# workaround orthographic projection
from mpl_toolkits.mplot3d import proj3d
 
def _orthogonal_proj(zfront, zback):
    a = (zfront+zback)/(zfront-zback)
    b = -2*(zfront*zback)/(zfront-zback)
    # -0.0001 added for numerical stability as suggested in:
    # http://stackoverflow.com/questions/23840756
    return np.array([[1,0,0,0],
                        [0,1,0,0],
                        [0,0,a,b],
                        [0,0,-0.0001,zback]])
from ROOT import *
import re
import os
import sys
import argparse
import fnmatch
import math
from array import array
import numpy as np

def CheckBit(number,bitpos):
    bitdigit = 1
    res = bool(number&(bitdigit<<bitpos))
    return res

class LeafManager():
    """
    Class to manage TTree branch leafs, making sure they exist.
    """
    def __init__(self, fname, t_in):
        self.fname = fname
        self.tree = t_in
        self.absent_leaves = set()
        self.error_prefix = '[LeafManager]: '
        
    def getLeaf(self, leaf):
        if not isinstance(leaf, str):
            m = 'The leaf must be a string.'
            raise TypeError(self.error_prefix + m)
        try:
            obj = self.tree.GetListOfBranches().FindObject(leaf)
            name = obj.GetName()
            getAttr = lambda x : getattr(self.tree, x)
            return getAttr(leaf)
        except ReferenceError:
            if leaf not in self.absent_leaves:
                m = 'WARNING: leaf ' + leaf + ' does not exist in file ' + self.fname + '.'
                print(self.error_prefix + m)
                self.absent_leaves.add(leaf)
            return 0.

def getTriggerEffSig(indir, outdir, sample, fileName, channels, htcut):
    
    # -- Check if outdir exists, if not create it
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    if not os.path.exists( os.path.join(outdir, sample) ):
        os.makedirs( os.path.join(outdir, sample) )
    outdir = os.path.join(outdir, sample)

    
    # -- Define histograms
    h_MET, h_METonly, h_ALL= {},{},{}
    cat = channels
    #trg = ['9','10','11']#,'12','13','14', 'all']
    trg = ['MET','Tau','TauMET']
    var = ['met_et', 'HT20', 'mht_et', 'metnomu_et', 'mhtnomu_et', 'dau1_pt', 'dau2_pt']
    
    for i in cat:
        h_MET[i] = {}
        h_METonly[i] = {}
        h_ALL[i] = {}#TH1D('passALL_{}'.format(i),     '',6,0.,600.)
        for j in var:
            h_MET[i][j]={}
            h_METonly[i][j] = {}
            h_ALL[i][j] = TH1D('passALL_{}_{}'.format(i,j),     '',6,0.,600.)
            for k in trg:
                h_MET[i][j][k] = TH1D('passMET_{}_{}_{}'.format(i,j,k),     '',6,0.,600.)
                h_METonly[i][j][k] = TH1D('passMETonly_{}_{}_{}'.format(i,j,k),     '',6,0.,600.)


    isData = ('2018' in sample) # TODO

    fname = os.path.join(indir, 'SKIM_'+sample, fileName)
    f_in = TFile( fname )
    t_in = f_in.Get('HTauTauTree')

    sumweights=0
    fillVar = {}
    lf = LeafManager( fname, t_in )

    for entry in range(0,t_in.GetEntries()):
        t_in.GetEntry(entry)

        pairtype = lf.getLeaf( 'pairType' )
        mhh = lf.getLeaf( 'HHKin_mass' )
        if mhh<1:
            continue
        #        print('mass ok')
        nleps      = lf.getLeaf( 'nleps'      )
        nbjetscand = lf.getLeaf( 'nbjetscand' )
        isOS       = lf.getLeaf( 'isOS'       )

        dau1_eleiso = lf.getLeaf( 'dau1_eleMVAiso'    )
        dau1_muiso  = lf.getLeaf( 'dau1_iso'          )
        dau1_tauiso = lf.getLeaf( 'dau1_deepTauVsJet' )
        dau2_tauiso = lf.getLeaf( 'dau2_deepTauVsJet' )
        
        if pairtype==1 and (dau1_eleiso!=1 or dau2_tauiso<5):
            continue
        if pairtype==0 and (dau1_muiso>=0.15 or dau2_tauiso<5):
            continue
        if pairtype==2 and (dau1_tauiso<5 or dau2_tauiso<5):
            continue

        #((tauH_SVFIT_mass-116.)*(tauH_SVFIT_mass-116.))/(35.*35.) + ((bH_mass_raw-111.)*(bH_mass_raw-111.))/(45.*45.) <  1.0
        svfit_mass = lf.getLeaf('tauH_SVFIT_mass')
        bH_mass    = lf.getLeaf('bH_mass_raw')

        #mcut = ((svfit_mass-129.)*(svfit_mass-129.))/(53.*53.) + ((bH_mass-169.)*(bH_mass-169.))/(145.*145.) <  1.0
        #if mcut: # inverted elliptical mass cut (-> ttCR)
        #    continue
        
        #        print('passed selection')
        mcweight   = lf.getLeaf( "MC_weight" )
        pureweight = lf.getLeaf( "PUReweight" )
        trigsf     = lf.getLeaf( "trigSF" )
        lumi       = lf.getLeaf( "lumi" )
        idandiso   = lf.getLeaf( "IdAndIsoSF_deep_pt")
        
        if np.isnan(mcweight): mcweight=1
        if np.isnan(pureweight): pureweight=1
        if np.isnan(trigsf): trigsf=1
        if np.isnan(lumi): lumi=1
        if np.isnan(idandiso): idandiso=1

        evtW = pureweight*trigsf*lumi*idandiso
        if np.isnan(evtW): evtW=1
        if isData: evtW=1.
        sumweights+=evtW

        MET    = lf.getLeaf('met_et')
        HTfull = lf.getLeaf('HT20')

        for v in var:
            fillVar[v] = lf.getLeaf(v)
        for j in var:
            if fillVar[j]>600: fillVar[j]=599. # include overflow

        passMET = lf.getLeaf(   'isMETtrigger')
        passLEP = lf.getLeaf(   'isLeptrigger')
        passTAU = lf.getLeaf(   'isSingleTautrigger')
        passTAUMET = lf.getLeaf('isTauMETtrigger')

        trigBit = lf.getLeaf('pass_triggerbit')
        
        passReq = {}
        #req=[9,10,11]#,12,13,14]
        #if isData:
        #    req=[14,15,16]#,17,18,19]
        #
        #passReq['9']  = CheckBit(trigBit,req[0])
        #passReq['10'] = CheckBit(trigBit,req[1])
        #passReq['11'] = CheckBit(trigBit,req[2])
        ##passReq['12'] = CheckBit(trigBit,req[3])
        ##passReq['13'] = CheckBit(trigBit,req[4])
        ##passReq['14'] = CheckBit(trigBit,req[5])
        passReq['MET'] = passMET
        passReq['Tau'] = passTAU
        passReq['TauMET'] = passTAUMET
        #
        passMu   = passLEP and (CheckBit(trigBit,0) or CheckBit(trigBit,1))

        if passLEP:
            for i in cat:
                cond = (   ( i=='all'    and pairtype<3  ) 
                        or ( i=='mutau'  and pairtype==0 ) 
                        or ( i=='etau'   and pairtype==1 )  
                        or ( i=='tautau' and pairtype==2 )
                        or ( i=='mumu'   and pairtype==3 and passMu) 
                        or ( i=='ee'     and pairtype==4 ))
                if cond: 
                    for j in var:
                        h_ALL[i][j].Fill(fillVar[j],evtW)
                for j in var:
                    for k in trg:
                        if cond and passReq[k]:
                            h_MET[i][j][k].Fill(fillVar[j],evtW)
        else:
            for i in cat:
                cond = (   ( i=='all'    and pairtype<3  ) 
                        or ( i=='mutau'  and pairtype==0 ) 
                        or ( i=='etau'   and pairtype==1 )  
                        or ( i=='tautau' and pairtype==2 )
                        or ( i=='mumu'   and pairtype==3 and passMu ) 
                        or ( i=='ee'     and pairtype==4 ))
                for j in var:
                    for k in trg:
                        if cond and passReq[k]:
                            h_METonly[i][j][k].Fill(fillVar[j],evtW)


    file_id = ''.join( c for c in fileName[-10:] if c.isdigit() ) 
    outName = os.path.join(outdir, 'hist_eff_'+sample+'_'+file_id+'.'+htcut+'.root')
    print('Saving file {} at {} '.format(file_id, outName) )
    f_out = TFile(outName, 'RECREATE')
    f_out.cd()

    for i in cat:
        for j in var:
            h_ALL[i][j].Write('passALL_{}_{}'.format(i,j))
            for k in trg:
                h_MET[i][j][k].Write('pass{}_{}_{}'.format(k,i,j))
                h_METonly[i][j][k].Write('pass{}only_{}_{}'.format(k,i,j))

    f_out.Close()
    f_in.Close()

if __name__ == "__main__":

    # -- Parse input arguments
    parser = argparse.ArgumentParser(description='Command line parser')

    parser.add_argument('--indir',    dest='indir',    required=True, help='SKIM directory')
    parser.add_argument('--outdir',   dest='outdir',   required=True, help='output directory')
    parser.add_argument('--sample',   dest='sample',   required=True, help='Process name as in SKIM directory')
    parser.add_argument('--file',     dest='fileName', required=True, help='ID of input root file')
    parser.add_argument('--channels', dest='channels', required=True, nargs='+', type=str,
                        help='Select the channels over which the workflow will be run.' )
    parser.add_argument('--htcut', dest='htcut', default='metnomu200cut', help='Specifies a cut.')
    
    args = parser.parse_args()

    getTriggerEffSig(args.indir, args.outdir, args.sample, args.fileName, args.channels, args.htcut)

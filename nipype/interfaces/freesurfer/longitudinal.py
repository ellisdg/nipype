# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Provides interfaces to various longitudinal commands provided by freesurfer

   Change directory to provide relative paths for doctests
   >>> import os
   >>> filepath = os.path.dirname( os.path.realpath( __file__ ) )
   >>> datadir = os.path.realpath(os.path.join(filepath, '../../testing/data'))
   >>> os.chdir(datadir)

"""
__docformat__ = 'restructuredtext'

import os
#import itertools

from nipype.utils.filemanip import fname_presuffix
from nipype.interfaces.freesurfer.base import FSCommand, FSTraitedSpec
from nipype.interfaces.base import (TraitedSpec, File, traits,
                                    InputMultiPath, OutputMultiPath, isdefined)

from ... import logging
iflogger = logging.getLogger('interface')


class RobustTemplateInputSpec(FSTraitedSpec):
    # required
    in_files = InputMultiPath(File(exists=True), mandatory=True, argstr='--mov %s',
                             desc='input movable volumes to be aligned to common mean/median template')
    out_file = File('mri_robust_template_out.mgz', mandatory=True, usedefault=True, argstr='--template %s',
                           desc='output template volume (final mean/median image)')
    auto_detect_sensitivity = traits.Bool(argstr='--satit', xor=['outlier_sensitivity'], mandatory=True,
                                          desc='auto-detect good sensitivity (recommended for head or full brain scans)')
    outlier_sensitivity = traits.Float(argstr='--sat %.4f', xor=['auto_detect_sensitivity'], mandatory=True,
                                       desc='set outlier sensitivity manually (e.g. "--sat 4.685" ). Higher values mean ' +
                                       'less sensitivity.')
    # optional
    transform_outputs = InputMultiPath(File(exists=False),
                                       argstr='--lta %s', desc='output xforms to template (for each input)')
    intensity_scaling = traits.Bool(
        default_value=False, argstr='--iscale', desc='allow also intensity scaling (default off)')
    scaled_intensity_outputs = InputMultiPath(File(exists=False),
                                              argstr='--iscaleout %s',
                                              desc='final intensity scales (will activate --iscale)')
    subsample_threshold = traits.Int(
        argstr='--subsample %d', desc='subsample if dim > # on all axes (default no subs.)')
    average_metric = traits.Enum('median', 'mean', argstr='--average %d',
                                 desc='construct template from: 0 Mean, 1 Median (default)')
    initial_timepoint = traits.Int(
        argstr='--inittp %d', desc='use TP# for spacial init (default random), 0: no init')
    fixed_timepoint = traits.Bool(default_value=False, argstr='--fixtp',
                                  desc='map everthing to init TP# (init TP is not resampled)')
    no_iteration = traits.Bool(default_value=False, argstr='--noit',
                               desc='do not iterate, just create first template')
    initial_transforms = InputMultiPath(File(exists=True),
                                        argstr='--ixforms %s',
                                        desc='use initial transforms (lta) on source')
    in_intensity_scales = InputMultiPath(File(exists=True),
                                         argstr='--iscalein %s',
                                         desc='use initial intensity scales')

class RobustTemplateOutputSpec(TraitedSpec):
    out_file = File(
        exists=True, desc='output template volume (final mean/median image)')
    transform_outputs = OutputMultiPath(
        File(exists=True), desc="output xform files from moving to template")
    scaled_intensity_outputs = OutputMultiPath(
        File(exists=True), desc="output final intensity scales")


class RobustTemplate(FSCommand):
    """ construct an unbiased robust template for longitudinal volumes

    Examples
    --------
    >>> from nipype.interfaces.freesurfer import RobustTemplate
    >>> template = RobustTemplate()
    >>> template.inputs.in_files = ['structural.nii', 'functional.nii']
    >>> template.inputs.auto_detect_sensitivity = True
    >>> template.inputs.average_metric = 'mean'
    >>> template.inputs.initial_timepoint = 1
    >>> template.inputs.fixed_timepoint = True
    >>> template.inputs.no_iteration = True
    >>> template.inputs.subsample_threshold = 200
    >>> template.cmdline  #doctest: +NORMALIZE_WHITESPACE
    'mri_robust_template --satit --average 0 --fixtp --mov structural.nii functional.nii --inittp 1 --noit --template mri_robust_template_out.mgz --subsample 200'
    >>> template.inputs.out_file = 'T1.nii'
    >>> template.cmdline  #doctest: +NORMALIZE_WHITESPACE
    'mri_robust_template --satit --average 0 --fixtp --mov structural.nii functional.nii --inittp 1 --noit --template T1.nii --subsample 200'

    >>> template.inputs.transform_outputs = ['structural.lta', 'functional.lta']
    >>> template.inputs.scaled_intensity_outputs = ['structural-iscale.txt', 'functional-iscale.txt']
    >>> template.cmdline    #doctest: +NORMALIZE_WHITESPACE
    'mri_robust_template --satit --average 0 --fixtp --mov structural.nii functional.nii --inittp 1 --noit --template T1.nii --iscaleout structural-iscale.txt functional-iscale.txt --subsample 200 --lta structural.lta functional.lta'

    >>> template.run()  #doctest: +SKIP

    References
    ----------
    [https://surfer.nmr.mgh.harvard.edu/fswiki/mri_robust_template]

    """

    _cmd = 'mri_robust_template'
    input_spec = RobustTemplateInputSpec
    output_spec = RobustTemplateOutputSpec

    def _format_arg(self, name, spec, value):
        if name == 'average_metric':
            # return enumeration value
            return spec.argstr % {"mean": 0, "median": 1}[value]
        return super(RobustTemplate, self)._format_arg(name, spec, value)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_file'] = os.path.abspath(
            self.inputs.out_file)
        if isdefined(self.inputs.transform_outputs):
            outputs['transform_outputs'] = [os.path.abspath(
                x) for x in self.inputs.transform_outputs]
        if isdefined(self.inputs.scaled_intensity_outputs):
            outputs['scaled_intensity_outputs'] = [os.path.abspath(
                x) for x in self.inputs.scaled_intensity_outputs]
        return outputs


class FuseSegmentationsInputSpec(FSTraitedSpec):
    # required
    subject_id = traits.String(argstr='%s', position=-3,
                               desc="subject_id being processed")
    timepoints = InputMultiPath(
        traits.String(), mandatory=True, argstr='%s', position=-2,
        desc='subject_ids or timepoints to be processed')
    out_file = File(exists=False, mandatory=True, position=-1,
                    desc="output fused segmentation file")
    in_segmentations = InputMultiPath(
        File(exists=True), argstr="-a %s", mandatory=True,
        desc="name of aseg file to use (default: aseg.mgz) \
        must include the aseg files for all the given timepoints")
    in_segmentations_noCC = InputMultiPath(
        File(exists=True), argstr="-c %s", mandatory=True,
        desc="name of aseg file w/o CC labels (default: aseg.auto_noCCseg.mgz) \
        must include the corresponding file for all the given timepoints")
    in_norms = InputMultiPath(
        File(exists=True), argstr="-n %s", mandatory=True,
        desc="-n <filename>  - name of norm file to use (default: norm.mgs) \
        must include the corresponding norm file for all given timepoints \
        as well as for the current subject")

class FuseSegmentationsOutputSpec(TraitedSpec):
    out_file = File(exists=False, desc="output fused segmentation file")

class FuseSegmentations(FSCommand):

    """ fuse segmentations together from multiple timepoints

    Examples
    --------
    >>> from nipype.interfaces.freesurfer import FuseSegmentations
    >>> fuse = FuseSegmentations()
    >>> fuse.inputs.subject_id = 'tp.long.A.template'
    >>> fuse.inputs.timepoints = ['tp1', 'tp2']
    >>> fuse.inputs.out_file = 'tp.long.A.template/mri/aseg.fused.mgz' #doctest: +SKIP
    >>> fuse.inputs.in_segmentations = ['tp1/mri/aseg.presurf.mgz', 'tp1/mri/aseg.presurf.mgz'] #doctest: +SKIP
    >>> fuse.inputs.in_segmentations_noCC = ['tp1/mri/aseg.auto_noCCseg.mgz', 'tp1/mri/aseg.auto_noCCseg.mgz'] #doctest: +SKIP
    >>> fuse.inputs.in_norms = ['tp1/mri/norm.mgz', 'tp1/mri/norm.mgz', 'tp.long.A.template/mri/norm.mgz'] #doctest: +SKIP
    >>> fuse.cmdline #doctest: +SKIP
    """

    _cmd = 'mri_fuse_segmentations'
    input_spec = FuseSegmentationsInputSpec
    output_spec = FuseSegmentationsOutputSpec

    def _format_arg(self, name, spec, value):
        if name in ('in_segmentations', 'in_segmentations_noCC', 'in_norms'):
            # return enumeration value
            return spec.argstr % os.path.basename(value[0])
        return super(FuseSegmentations, self)._format_arg(name, spec, value)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_file'] = os.path.abspath(
            self.inputs.out_file)
        return outputs
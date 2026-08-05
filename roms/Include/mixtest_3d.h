/*
*******************************************************************************
** Copyright (c) 2002-2021 The ROMS/TOMS Group                               **
**   Licensed under a MIT/X style license                                    **
**   See License_ROMS.txt                                                    **
*******************************************************************************
**
** Options for Test Mix.
**
** Application flag:   MIXTEST-3D
** Input script:       mixtest-3d.in
*/


/* BASICS (from norkyst) */
#define SOLVE3D            /* define if solving 3D primitive equations */
#define DJ_GRADPS          /* Splines density  Jacobian (Shchepetkin, 2000) */
#define NONLIN_EOS         /* define if using nonlinear equation of state */
#define SALINITY           /* define if using salinity */
#define LIMIT_BSTRESS      /* Limit bottom stress to maintain bottom velocity direction */
#define UV_QDRAG           /* turn ON quadratic bottom friction */

/* MIXING (from norkyst) */
#define UV_VIS2            /* turn ON Laplacian horizontal mixing */
#define TS_DIF2            /* turn ON Laplacian horizontal mixing */
#undef TS_MIX_STABILITY    /* weighting diffusion between two time levels */ 
#define MIX_GEO_TS         /* mixing on geopotential (constant Z) surfaces */
#define MIX_S_UV           /* mixing on model surfaces */

#undef RI_SPLINES         /* conservative, parabolic splines reconstruction */
#undef SPLINES_VVISC      /* splines reconstruction of vertical viscosity */
#undef SPLINES_VDIFF      /* splines reconstruction of vertical diffusion */

#undef LIMIT_VDIFF         /* do not impose an upper limit on vertical diffusion */
#undef LIMIT_VVISC         /* do not impose an upper limit on vertical viscosity */

#define GLS_MIXING
#define N2S2_HORAVG       /* Activate horizontal smoothing of buoyancy/shear */
#undef CRAIG_BANNER       /* Craig and Banner wave breaking surface flux */
#define CANUTO_A          /* Canuto A-stability function formulation */
#undef CHARNOK            /* Charnok surface roughness from wind stress */
#undef  K_C4ADVECTION


/* ANALYTICAL */
#define ANA_SMFLUX        /* will add this as file input later */
#define ANA_STFLUX
#define ANA_SSFLUX
#define ANA_BTFLUX
#define ANA_BSFLUX


/* Structure drag parametrization */
#define STRUCTURE_MIXING

/* Idealized testing */
#undef UV_COR             /* turn OFF Coriolis term */
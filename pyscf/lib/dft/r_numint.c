/*
 * Author: Qiming Sun <osirpt.sun@gmail.com>
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <complex.h>
#include "cint.h"
#include "gto/grid_ao_drv.h"
#include "np_helper/np_helper.h"
#include "vhf/fblas.h"
#include <assert.h>

#define BOXSIZE         56

int VXCao_empty_blocks(char *empty, unsigned char *non0table, int *shls_slice,
                       int *ao_loc);

static void dot_ao_dm(double complex *vm, double complex *ao, double complex *dm,
                      int nao, int nocc, int ngrids, int bgrids,
                      unsigned char *non0table, int *shls_slice, int *ao_loc)
{
        int nbox = (nao+BOXSIZE-1) / BOXSIZE;
        char empty[nbox];
        int has0 = VXCao_empty_blocks(empty, non0table, shls_slice, ao_loc);

        const char TRANS_T = 'T';
        const char TRANS_N = 'N';
        const double complex Z1 = 1;
        double complex beta = 0;

        if (has0) {
                int box_id, bas_id, b0, blen, i, j;
                for (box_id = 0; box_id < nbox; box_id++) {
                        if (!empty[box_id]) {
                                b0 = box_id * BOXSIZE;
                                blen = MIN(nao-b0, BOXSIZE);
                                zgemm_(&TRANS_N, &TRANS_T, &bgrids, &nocc, &blen,
                                       &Z1, ao+b0*ngrids, &ngrids, dm+b0*nocc, &nocc,
                                       &beta, vm, &ngrids);
                                beta = 1.0;
                        }
                }
                if (beta == 0) { // all empty
                        for (i = 0; i < nocc; i++) {
                                for (j = 0; j < bgrids; j++) {
                                        vm[i*ngrids+j] = 0;
                                }
                        }
                }
        } else {
                zgemm_(&TRANS_N, &TRANS_T, &bgrids, &nocc, &nao,
                       &Z1, ao, &ngrids, dm, &nocc, &beta, vm, &ngrids);
        }
}


/* vm[nocc,ngrids] = ao[i,ngrids] * dm[i,nocc] */
void VXCzdot_ao_dm(double complex *vm, double complex *ao, double complex *dm,
                   int nao, int nocc, int ngrids, int nbas,
                   unsigned char *non0table, int *shls_slice, int *ao_loc)
{
        const int nblk = (ngrids+BLKSIZE-1) / BLKSIZE;

#pragma omp parallel default(none) \
        shared(vm, ao, dm, nao, nocc, ngrids, nbas, \
               non0table, shls_slice, ao_loc)
{
        int ip, ib;
#pragma omp for nowait schedule(static)
        for (ib = 0; ib < nblk; ib++) {
                ip = ib * BLKSIZE;
                dot_ao_dm(vm+ip, ao+ip, dm,
                          nao, nocc, ngrids, MIN(ngrids-ip, BLKSIZE),
                          non0table+ib*nbas, shls_slice, ao_loc);
        }
}
}



/* conj(vv[n,m]) = ao1[n,ngrids] * conj(ao2[m,ngrids]) */
static void dot_ao_ao(double complex *vv, double complex *ao1, double complex *ao2,
                      int nao, int ngrids, int bgrids, int hermi,
                      unsigned char *non0table, int *shls_slice, int *ao_loc)
{
        int nbox = (nao+BOXSIZE-1) / BOXSIZE;
        char empty[nbox];
        int has0 = VXCao_empty_blocks(empty, non0table, shls_slice, ao_loc);

        const char TRANS_C = 'C';
        const char TRANS_N = 'N';
        const double complex Z1 = 1;
        if (has0) {
                int ib, jb, b0i, b0j, leni, lenj;
                int j1 = nbox;

                for (ib = 0; ib < nbox; ib++) {
                if (!empty[ib]) {
                        b0i = ib * BOXSIZE;
                        leni = MIN(nao-b0i, BOXSIZE);
                        if (hermi) {
                                j1 = ib + 1;
                        }
                        for (jb = 0; jb < j1; jb++) {
                        if (!empty[jb]) {
                                b0j = jb * BOXSIZE;
                                lenj = MIN(nao-b0j, BOXSIZE);
                                zgemm_(&TRANS_C, &TRANS_N, &lenj, &leni, &bgrids, &Z1,
                                       ao2+b0j*ngrids, &ngrids, ao1+b0i*ngrids, &ngrids,
                                       &Z1, vv+b0i*nao+b0j, &nao);
                        } }
                } }
        } else {
                zgemm_(&TRANS_C, &TRANS_N, &nao, &nao, &bgrids,
                       &Z1, ao2, &ngrids, ao1, &ngrids, &Z1, vv, &nao);
        }
}


/* vv[nao,nao] = conj(ao1[i,nao]) * ao2[i,nao] */
void VXCzdot_ao_ao(double complex *vv, double complex *ao1, double complex *ao2,
                   int nao, int ngrids, int nbas, int hermi,
                   unsigned char *non0table, int *shls_slice, int *ao_loc)
{
        const int nblk = (ngrids+BLKSIZE-1) / BLKSIZE;
        memset(vv, 0, sizeof(double complex) * nao * nao);

#pragma omp parallel default(none) \
        shared(vv, ao1, ao2, nao, ngrids, nbas, hermi, \
               non0table, shls_slice, ao_loc)
{
        int ip, ib;
        double complex *v_priv = calloc(nao*nao+2, sizeof(double complex));
#pragma omp for nowait schedule(static)
        for (ib = 0; ib < nblk; ib++) {
                ip = ib * BLKSIZE;
                dot_ao_ao(v_priv, ao1+ip, ao2+ip,
                          nao, ngrids, MIN(ngrids-ip, BLKSIZE), hermi,
                          non0table+ib*nbas, shls_slice, ao_loc);
        }
#pragma omp critical
        {
                for (ip = 0; ip < nao*nao; ip++) {
                        vv[ip] += conj(v_priv[ip]);
                }
        }
        free(v_priv);
}
        if (hermi != 0) {
                NPzhermi_triu(nao, vv, hermi);
        }
}

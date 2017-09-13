#include<stdio.h>
#include<stdlib.h>
#include <omp.h>

/*
!
!
!Compute Y += A*X for CSR matrix A and dense vectors X,Y
! From scipy/sparse/sparsetools/csr.h
!
!
! Input Arguments:
!   I  n_row         - number of rows in A
!   I  n_col         - number of columns in A
!   I  Ap[n_row+1]   - row pointer
!   I  Aj[nnz(A)]    - column indices
!   T  Ax[nnz(A)]    - nonzeros
!   T  Xx[n_col]     - input vector
!
! Output Arguments:
!  T  Yx[n_row]     - output vector
!
! Note:
!   Output array Yx must be preallocated
!
!   Complexity: Linear.  Specifically O(nnz(A) + n_row)
*/
extern "C" void scsr_matvec(int nrow, int ncol, int nnz, int *Ap, int *Aj, 
    float *Ax, float *Xx, float *Yx)
{

  int i, jj;
  float sum = 0.0;

  # pragma omp parallel \
  shared (nrow, Yx, Ap, Ax, Xx, Aj) \
  private (i, jj, sum)
  {
    #pragma omp for
    for(i = 0; i < nrow; i++){
      sum = Yx[i];
      for(jj = Ap[i]; jj < Ap[i+1]; jj++){
        sum += Ax[jj] * Xx[Aj[jj]];
      }
      Yx[i] = sum;
    }
  }
}


extern "C" void dcsr_matvec(int nrow, int ncol, int nnz, int *Ap, int *Aj, 
    double *Ax, double *Xx, double *Yx)
{

  int i, jj;
  double sum = 0.0;

  # pragma omp parallel \
  shared (nrow, Yx, Ap, Ax, Xx, Aj) \
  private (i, jj, sum)
  {
    #pragma omp for
    for(i = 0; i < nrow; i++){
      sum = Yx[i];
      for(jj = Ap[i]; jj < Ap[i+1]; jj++){
        sum += Ax[jj] * Xx[Aj[jj]];
      }
      Yx[i] = sum;
    }
  }
}


/*
 * Compute Y += A*X for CSC matrix A and dense vectors X,Y
 * From scipy/sparse/sparsetools/csc.h
 *
 *
 * Input Arguments:
 *   I  n_row         - number of rows in A
 *   I  n_col         - number of columns in A
 *   I  Ap[n_row+1]   - column pointer
 *   I  Ai[nnz(A)]    - row indices
 *   T  Ax[n_col]     - nonzeros
 *   T  Xx[n_col]     - input vector
 *
 * Output Arguments:
 *   T  Yx[n_row]     - output vector
 *
 * Note:
 *   Output array Yx must be preallocated
 *
 *   Complexity: Linear.  Specifically O(nnz(A) + n_col)
 *
 */
extern "C" void scsc_matvec(int n_row, int n_col, int nnz,
            int *Ap, int *Ai, float *Ax, float *Xx, float *Yx)
{
    int col_start, col_end, j, ii, i;

    for( j = 0; j < n_col; j++){
        col_start = Ap[j];
        col_end   = Ap[j+1];

        for( ii = col_start; ii < col_end; ii++){
            i    = Ai[ii];
            Yx[i] += Ax[ii] * Xx[j];
        }
    }
}

extern "C" void dcsc_matvec(int n_row, int n_col, int nnz,
            int *Ap, int *Ai, double *Ax, double *Xx, double *Yx)
{
    int col_start, col_end, j, ii, i;

    for( j = 0; j < n_col; j++){
        col_start = Ap[j];
        col_end   = Ap[j+1];

        for( ii = col_start; ii < col_end; ii++){
            i    = Ai[ii];
            Yx[i] += Ax[ii] * Xx[j];
        }
    }
}
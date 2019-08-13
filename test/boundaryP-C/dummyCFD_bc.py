#!/usr/bin/env python2
from __future__ import print_function, division
import cPickle
import sys

try:
    from mpi4py import MPI
    from cplpy import CPL 
    import numpy as np
except ImportError as exc:
    print("ERROR: ", sys.exc_info()[0], exc, file=sys.stderr)
    MPI.COMM_WORLD.Abort(errorcode=1)


cpllib = CPL()

cpllib.set("output_mode", 1)


try:
    # Load parameters for the run
    params = cPickle.load(open("cfd_params.dic", "rb"))

    # Parameters of the cpu topology (cartesian grid)
    NPx = params["npx"]
    NPy = params["npy"]
    NPz = params["npz"]

    # Parameters of the mesh topology (cartesian grid)
    NCx = params["ncx"]
    NCy = params["ncy"]
    NCz = params["ncz"]

    # Parameters of the domain
    Lx = params["lx"]
    Ly = params["ly"]
    Lz = params["lz"]
except:
    print("ERROR: ", sys.exc_info()[0], file=sys.stderr)
    MPI.COMM_WORLD.Abort(errorcode=1)

nsteps = 3
dt = 1.0
xyz_orig = np.array([0.0, 0.0, 0.0], order='F', dtype=np.float64)
NProcs = NPx*NPy*NPz
ncxyz = np.array([NCx, NCy, NCz], order='F', dtype=np.int32)
xyzL = np.array([Lx, Ly, Lz], order='F', dtype=np.float64)

# Create communicators and check that number of processors is consistent
realm_comm = cpllib.init(cpllib.CFD_REALM)
nprocs_realm = realm_comm.Get_size()

if (nprocs_realm != NProcs):
    print("ERROR: ", "Number of processes is not coherent.", file=sys.stderr)
    MPI.COMM_WORLD.Abort(errorcode=1)

# Create cartesian communicator and initialize
cpllib.set_timing(0, nsteps, dt)
cart_comm = realm_comm.Create_cart([NPx, NPy, NPz])
cpllib.setup_cfd(cart_comm, xyzL, xyz_orig, ncxyz)

my_coords = cart_comm.Get_coords(cart_comm.Get_rank())
my_coords = np.array(my_coords, order='F', dtype=np.int32)
olap_limits = cpllib.get_olap_limits()

# Constrained region cell limits and number of cells
cnstFRegion = cpllib.get_cnst_limits()
cnstFPortion = cpllib.my_proc_portion(cnstFRegion)
[cnstncx, cnstncy, cnstncz] = cpllib.get_no_cells(cnstFPortion)

# Velocity averaging region cell limits and number of cells
BCRegion = cpllib.get_bnry_limits()
BCPortion = cpllib.my_proc_portion(BCRegion)
[BCncx, BCncy, BCncz] = cpllib.get_no_cells(BCPortion)

# Buffers send/recv
send_array = np.zeros((9, cnstncx, cnstncy, cnstncz), order='F',
                         dtype=np.float64)
recv_array = np.zeros((5, BCncx, BCncy, BCncz), order='F',
                      dtype=np.float64)

# Initial setup communication 
cpllib.send(send_array, cnstFRegion)
cpllib.recv(recv_array, BCRegion)


for step in xrange(nsteps):
    cpllib.send(send_array, cnstFRegion)
    cpllib.recv(recv_array, BCRegion)
    cpllib.dump_region(BCRegion, recv_array, "cfd_bc%d.dat"%step, realm_comm,                                                                                                                                                            
            components={0:None, 1:None, 2:None, 4:None},  coords="other")
    
cpllib.finalize()

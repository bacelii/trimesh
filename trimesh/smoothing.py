import numpy as np

try:
    from scipy.sparse.linalg import spsolve
    from scipy.sparse import coo_matrix, eye
except ImportError:
    pass

from . import triangles
from .util import unitize
from .geometry import index_sparse
from .triangles import mass_properties


def filter_laplacian(mesh,
                     lamb=0.5,
                     iterations=10,
                     implicit_time_integration=False,
                     volume_constraint=True,
                     laplacian_operator=None):
    """
    Smooth a mesh in-place using laplacian smoothing.
    Articles
    1 - "Improved Laplacian Smoothing of Noisy Surface Meshes"
       J. Vollmer, R. Mencl, and H. Muller
    2 - "Implicit Fairing of Irregular Meshes using Diffusion
       and Curvature Flow". M. Desbrun,  M. Meyer,
       P. Schroder, A.H.B. Caltech
    Parameters
    ------------
    mesh : trimesh.Trimesh
    Mesh to be smoothed in place
    lamb : float
    Diffusion speed constant
    If   0.0, no diffusion
    If > 0.0, diffusion occurs
    implicit_time_integration: boolean
    if False: explicit time integration
        -lamb <= 1.0 - Stability Limit (Article 1)
    if True: implicit time integration
        -lamb no limit (Article 2)
    iterations : int
    Number of passes to run filter
    laplacian_operator : None or scipy.sparse.coo.coo_matrix
    Sparse matrix laplacian operator
    Will be autogenerated if None
    """

    # if the laplacian operator was not passed create it here
    if laplacian_operator is None:
        laplacian_operator = laplacian_calculation(mesh)

    # save initial volume
    if volume_constraint:
        vol_ini = mesh.volume

    # get mesh vertices and faces as vanilla numpy array
    vertices = mesh.vertices.copy().view(np.ndarray)
    faces = mesh.faces.copy().view(np.ndarray)

    # Set matrix for linear system of equations
    if implicit_time_integration:
        dlap = laplacian_operator.shape[0]
        AA = eye(dlap) + lamb * (eye(dlap) - laplacian_operator)

    # Number of passes
    for _index in range(iterations):
        # Classic Explicit Time Integration - Article 1
        if not implicit_time_integration:
            dot = laplacian_operator.dot(vertices) - vertices
            vertices += lamb * dot

        # Implicit Time Integration - Article 2
        else:
            vertices = spsolve(AA, vertices)

        # volume constraint
        if volume_constraint:
            # find the volume with new vertex positions
            vol_new = triangles.mass_properties(
                vertices[faces], skip_inertia=True)["volume"]
            # scale by volume ratio
            vertices *= ((vol_ini / vol_new) ** (1.0 / 3.0))

    # assign modified vertices back to mesh
    mesh.vertices = vertices
    return mesh


def filter_humphrey(mesh,
                    alpha=0.1,
                    beta=0.5,
                    iterations=10,
                    laplacian_operator=None):
    """
    Smooth a mesh in-place using laplacian smoothing
    and Humphrey filtering.
    Articles
    "Improved Laplacian Smoothing of Noisy Surface Meshes"
    J. Vollmer, R. Mencl, and H. Muller
    Parameters
    ------------
    mesh : trimesh.Trimesh
      Mesh to be smoothed in place
    alpha : float
      Controls shrinkage, range is 0.0 - 1.0
      If 0.0, not considered
      If 1.0, no smoothing
    beta : float
      Controls how aggressive smoothing is
      If 0.0, no smoothing
      If 1.0, full aggressiveness
    iterations : int
      Number of passes to run filter
    laplacian_operator : None or scipy.sparse.coo.coo_matrix
      Sparse matrix laplacian operator
      Will be autogenerated if None
    """
    # if the laplacian operator was not passed create it here
    if laplacian_operator is None:
        laplacian_operator = laplacian_calculation(mesh)

    # get mesh vertices as vanilla numpy array
    vertices = mesh.vertices.copy().view(np.ndarray)
    # save original unmodified vertices
    original = vertices.copy()

    # run through iterations of filter
    for _index in range(iterations):
        vert_q = vertices.copy()
        vertices = laplacian_operator.dot(vertices)
        vert_b = vertices - (alpha * original + (1.0 - alpha) * vert_q)
        vertices -= (beta * vert_b + (1.0 - beta) *
                     laplacian_operator.dot(vert_b))

    # assign modified vertices back to mesh
    mesh.vertices = vertices
    return mesh


def filter_taubin(mesh,
                  lamb=0.5,
                  nu=0.5,
                  iterations=10,
                  laplacian_operator=None):
    """
    Smooth a mesh in-place using laplacian smoothing
    and taubin filtering.
    Articles
    "Improved Laplacian Smoothing of Noisy Surface Meshes"
    J. Vollmer, R. Mencl, and H. Muller
    Parameters
    ------------
    mesh : trimesh.Trimesh
      Mesh to be smoothed in place.
    lamb : float
      Controls shrinkage, range is 0.0 - 1.0
    nu : float
      Controls dilation, range is 0.0 - 1.0
      Nu shall be between 0.0 < 1.0/lambda - 1.0/nu < 0.1
    iterations : int
      Number of passes to run the filter
    laplacian_operator : None or scipy.sparse.coo.coo_matrix
      Sparse matrix laplacian operator
      Will be autogenerated if None
    """
    # if the laplacian operator was not passed create it here
    if laplacian_operator is None:
        laplacian_operator = laplacian_calculation(mesh)

    # get mesh vertices as vanilla numpy array
    vertices = mesh.vertices.copy().view(np.ndarray)

    # run through multiple passes of the filter
    for index in range(iterations):
        # do a sparse dot product on the vertices
        dot = laplacian_operator.dot(vertices) - vertices
        # alternate shrinkage and dilation
        if index % 2 == 0:
            vertices += lamb * dot
        else:
            vertices -= nu * dot

    # assign updated vertices back to mesh
    mesh.vertices = vertices
    return mesh

def filter_mut_dif_laplacian(mesh,
                            lamb=0.5,
                            iterations=10,
                            volume_constraint=True, 
                            laplacian_operator=None):
  """
  Smooth a mesh in-place using laplacian smoothing using a mutable difusion laplacian
  Articles
    Barroqueiro, B., Andrade-Campos, A., Dias-de-Oliveira, J., and Valente, R. (January 21, 2021). 
    "Bridging between topology optimization and additive manufacturing via Laplacian smoothing." ASME. J. Mech. Des.
  Parameters
  ------------
  mesh : trimesh.Trimesh
  Mesh to be smoothed in place
  lamb : float
  Diffusion speed constant
  If   0.0, no diffusion
  If > 0.0, diffusion occours 
  iterations : int
  Number of passes to run filter
  laplacian_operator : None or scipy.sparse.coo.coo_matrix
  Sparse matrix laplacian operator
  Will be autogenerated if None
  """
  
  # if the laplacian operator was not passed create it here
  if laplacian_operator is None:
        laplacian_operator = laplacian_calculation(mesh)

  # Set volume constraint
  if volume_constraint==True:
        v_ini=mesh.volume

  # get mesh vertices as vanilla numpy array
  vertices = mesh.vertices.copy().view(np.ndarray)
  faces    = mesh.faces.copy().view(np.ndarray)
  eps=0.01*(np.max(mesh.area_faces)**0.5)

  # Number of passes
  for _index in range(iterations):
        
    # Mutable difusion
    normals=get_vertices_normals(mesh)
    qi=laplacian_operator.dot(vertices)
    pi_qi = vertices-qi
    adil = np.abs((normals*pi_qi).dot(np.ones((3,1))))
    adil=1.0/np.maximum(1e-12,adil)
    lamber=np.maximum(0.2*lamb, np.minimum(1.0,lamb*adil/np.mean(adil)))

    #Filter
    dot = laplacian_operator.dot(vertices) - vertices
    vertices += lamber * dot
                
    # Volume constraint
    if volume_constraint==True:
          vol=mass_properties(vertices[faces],skip_inertia=True)["volume"]
          if _index ==0:
                slope=dilate_slope(vertices,faces,normals,vol,eps)
          vertices += normals*slope*(v_ini-vol)
         
  # assign modified vertices back to mesh
  mesh.vertices = vertices

  return mesh


def laplacian_calculation(mesh, equal_weight=True,pinned_vertices=[]):
    """
    Calculate a sparse matrix for laplacian operations.
    Parameters
    -------------
    mesh : trimesh.Trimesh
      Input geometry
    equal_weight : bool
      If True, all neighbors will be considered equally
      If False, all neighbors will be weighted by inverse distance
    Returns
    ----------
    laplacian : scipy.sparse.coo.coo_matrix
      Laplacian operator
    """
    # get the vertex neighbors from the cache
    neighbors = mesh.vertex_neighbors
    
    # if a node is pinned, it will average his coordinates by himself
    # in practice it will not move
    for i in  pinned_vertices:
      neighbors[i]=[i]
    
    # avoid hitting crc checks in loops
    vertices = mesh.vertices.view(np.ndarray)

    # stack neighbors to 1D arrays
    col = np.concatenate(neighbors)
    row = np.concatenate([[i] * len(n)
                          for i, n in enumerate(neighbors)])

    if equal_weight:
        # equal weights for each neighbor
        data = np.concatenate([[1.0 / len(n)] * len(n)
                               for n in neighbors])
    else:
        # umbrella weights, distance-weighted
        # use dot product of ones to replace array.sum(axis=1)
        ones = np.ones(3)
        # the distance from verticesex to neighbors
        norms = [1.0 / np.maximum(1e-6, np.sqrt(np.dot((vertices[i] - vertices[n]) ** 2, ones))) for i, n in enumerate(neighbors)]
        # normalize group and stack into single array
        data = np.concatenate([i / i.sum() for i in norms])

    # create the sparse matrix
    matrix = coo_matrix((data, (row, col)),
                        shape=[len(vertices)] * 2)

    return matrix

def get_vertices_normals(mesh):
  """
  Compute Vertex normals using equal weighting of neighbors faces.
  Parameters
    -------------
    mesh : trimesh.Trimesh
      Input geometry
    Returns
    ----------
    vertices_normals: array
      Vertices normals
  """
  
  # get mesh vertices and faces
  vertices=mesh.vertices
  faces=mesh.faces

  # get face normals
  face_normals=mesh.face_normals

  # Compute Vert normals
  vert_normals = index_sparse(len(vertices),faces).dot(face_normals)

  return unitize(vert_normals)

def dilate_slope(vertices,faces,normals,v,eps):
  """
  Get de derivate of dilation scalar by the volume variation by finite diferences
  Thus, Vertices += vertex_normals*dilate_slope*(Initial_Volume - Srinked_Volume)
  Parameters
    -------------
    mesh : trimesh.Trimesh
      Input geometry
    vertices: mesh.vertices
    faces: mesh.faces
    normals: array
      vertices normals
    Returns
    ----------
    dilate_slope: float
      derivative
  """

  #finite diference derivative  
  vertices2 = vertices + normals*eps
  v2=mass_properties(vertices2[faces],skip_inertia=True)["volume"]

  return (eps)/(v2-v)

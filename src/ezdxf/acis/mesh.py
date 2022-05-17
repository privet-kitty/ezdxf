#  Copyright (c) 2022, Manfred Moitzi
#  License: MIT License
from __future__ import annotations
from typing import List, Iterator, Sequence, Optional
from ezdxf.render import MeshVertexMerger, MeshTransformer
from ezdxf.math import Matrix44, Vec3
from .entities import Body, Lump, NONE_REF


def mesh_from_body(body: Body, merge_lumps=True) -> List[MeshTransformer]:
    """Returns a list of :class:`~ezdxf.render.MeshTransformer` instances from
    the given ACIS :class:`Body` entity.
    The list contains multiple meshes if `merge_lumps` is ``False`` or just a
    singe mesh if `merge_lumps` is ``True``.

    The ACIS format stores the faces in counter-clockwise orientation where the
    face-normal points outwards (away) from the solid body (material).

    .. note::

        This function returns meshes build up only from flat polygonal
        :class:`Face` entities, for a tessellation of more complex ACIS
        entities (spline surfaces, tori, cones, ...) is an ACIS kernel
        required which `ezdxf` does not provide.

    Args:
        body: ACIS entity of type :class:`Body`
        merge_lumps: returns all :class:`Lump` entities
            from a body as a single mesh if ``True`` otherwise each :class:`Lump`
            entity is a separated mesh

    Raises:
        TypeError: given `body` entity has invalid type

    """
    if not isinstance(body, Body):
        raise TypeError(f"expected a body entity, got: {type(body)}")

    meshes: List[MeshTransformer] = []
    builder = MeshVertexMerger()
    for faces in flat_polygon_faces_from_body(body):
        for face in faces:
            builder.add_face(face)
        if not merge_lumps:
            meshes.append(MeshTransformer.from_builder(builder))
            builder = MeshVertexMerger()
    if merge_lumps:
        meshes.append(MeshTransformer.from_builder(builder))
    return meshes


def flat_polygon_faces_from_body(
    body: Body,
) -> Iterator[List[Sequence[Vec3]]]:
    """Yields all flat polygon faces from all lumps in the given
    :class:`Body` entity.
    Yields a separated list of faces for each linked :class:`Lump` entity.

    Args:
        body: ACIS entity of type :class:`Body`

    Raises:
        TypeError: given `body` entity has invalid type

    """

    if not isinstance(body, Body):
        raise TypeError(f"expected a body entity, got: {type(body)}")
    lump = body.lump
    transform = body.transform

    m: Optional[Matrix44] = None
    if not transform.is_none:
        m = transform.matrix
    while not lump.is_none:
        yield list(flat_polygon_faces_from_lump(lump, m))
        lump = lump.next_lump


def flat_polygon_faces_from_lump(
    lump: Lump, m: Matrix44 = None
) -> Iterator[Sequence[Vec3]]:
    """Yields all flat polygon faces from the given :class:`Lump` entity as
    sequence of :class:`~ezdxf.math.Vec3` instances. Applies the transformation
    :class:`~ezdxf.math.Matrix44` `m` to all vertices if not ``None``.

    Args:
        lump: :class:`Lump` entity
        m: optional transformation matrix

    Raises:
        TypeError: `lump` has invalid ACIS type

    """
    if not isinstance(lump, Lump):
        raise TypeError(f"expected a lump entity, got: {type(lump)}")

    shell = lump.shell
    if shell.is_none:
        return  # not a shell
    vertices: List[Vec3] = []
    face = shell.face
    while not face.is_none:
        first_coedge = NONE_REF
        vertices.clear()
        if face.surface.type == "plane-surface":
            try:
                first_coedge = face.loop.coedge
            except AttributeError:  # loop is a none-entity
                pass
        coedge = first_coedge
        while not coedge.is_none:  # invalid coedge or face is not closed
            # the edge entity contains the vertices and the curve type
            edge = coedge.edge
            try:
                # only straight lines as face edges supported:
                if edge.curve.type != "straight-curve":
                    break
                # add the first edge vertex to the face vertices
                if coedge.sense:  # reversed sense of the underlying edge
                    vertices.append(edge.end_vertex.point.location)
                else:  # same sense as the underlying edge
                    vertices.append(edge.start_vertex.point.location)
            except AttributeError:
                # one of the involved entities is a none-entity or an
                # incompatible entity type -> ignore this face!
                break
            coedge = coedge.next_coedge
            if coedge is first_coedge:  # a valid closed face
                if m is not None:
                    yield tuple(m.transform_vertices(vertices))
                else:
                    yield tuple(vertices)
                break
        face = face.next_face
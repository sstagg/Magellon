import array, sys
from ctypes import *
from comtypes import _safearray, GUID, IUnknown, com_interface_registry
from comtypes.partial import partial
_safearray_type_cache = {}
import numpy

################################################################
# This is THE PUBLIC function: the gateway to the SAFEARRAY functionality.
def _midlSAFEARRAY(itemtype):
    """This function mimics the 'SAFEARRAY(aType)' IDL idiom.  It
    returns a subtype of SAFEARRAY, instances will be built with a
    typecode VT_...  corresponding to the aType, which must be one of
    the supported ctypes.
    """
    try:
        return POINTER(_safearray_type_cache[itemtype])
    except KeyError:
        sa_type = _make_safearray_type(itemtype)
        _safearray_type_cache[itemtype] = sa_type
        return POINTER(sa_type)

def _make_safearray_type(itemtype):
    # Create and return a subclass of tagSAFEARRAY
    from comtypes.automation import _ctype_to_vartype, VT_RECORD, \
         VT_UNKNOWN, IDispatch, VT_DISPATCH

    meta = type(_safearray.tagSAFEARRAY)
    sa_type = meta.__new__(meta,
                           "SAFEARRAY_%s" % itemtype.__name__,
                           (_safearray.tagSAFEARRAY,), {})

    try:
        vartype = _ctype_to_vartype[itemtype]
        extra = None
    except KeyError:
        if issubclass(itemtype, Structure):
            try:
                guids = itemtype._recordinfo_
            except AttributeError:
                extra = None
            else:
                from comtypes.typeinfo import GetRecordInfoFromGuids
                extra = GetRecordInfoFromGuids(*guids)
            vartype = VT_RECORD
        elif issubclass(itemtype, POINTER(IDispatch)):
            vartype = VT_DISPATCH
            extra = pointer(itemtype._iid_)
        elif issubclass(itemtype, POINTER(IUnknown)):
            vartype = VT_UNKNOWN
            extra = pointer(itemtype._iid_)
        else:
            raise TypeError(itemtype)

    class _(partial, POINTER(sa_type)):
        # Should explain the ideas how SAFEARRAY is used in comtypes
        _itemtype_ = itemtype # a ctypes type
        _vartype_ = vartype # a VARTYPE value: VT_...
        _needsfree = False

##        @classmethod
        def create(cls, value, extra=None):
            """Create a POINTER(SAFEARRAY_...) instance of the correct
            type; value is an object containing the items to store.

            Python lists, tuples, and array.array instances containing
            compatible item types can be passed to create
            one-dimensional arrays.  To create multidimensional arrys,
            numpy arrays must be passed.
            """

            if "numpy" in sys.modules:
                numpy = sys.modules["numpy"]
                if isinstance(value, numpy.ndarray):
                    return cls.create_from_ndarray(value, extra)

            # For VT_UNKNOWN or VT_DISPATCH, extra must be a pointer to
            # the GUID of the interface.
            #
            # For VT_RECORD, extra must be a pointer to an IRecordInfo
            # describing the record.

            # XXX How to specify the lbound (3. parameter to CreateVectorEx)?
            # XXX How to write tests for lbound != 0?
            pa = _safearray.SafeArrayCreateVectorEx(cls._vartype_,
                                                    0,
                                                    len(value),
                                                    extra)
            if not pa:
                if cls._vartype_ == VT_RECORD and extra is None:
                    raise TypeError("Cannot create SAFEARRAY type VT_RECORD without IRecordInfo.")
                # Hm, there may be other reasons why the creation fails...
                raise MemoryError()
            # We now have a POINTER(tagSAFEARRAY) instance which we must cast
            # to the correct type:
            pa = cast(pa, cls)
            # Now, fill the data in:
            ptr = POINTER(cls._itemtype_)() # container for the values
            _safearray.SafeArrayAccessData(pa, byref(ptr))
            try:
                if isinstance(value, array.array):
                    addr, n = value.buffer_info()
                    nbytes = len(value) * sizeof(cls._itemtype_)
                    memmove(ptr, addr, nbytes)
                else:
                    for index, item in enumerate(value):
                        ptr[index] = item
            finally:
                _safearray.SafeArrayUnaccessData(pa)
            return pa
        create = classmethod(create)

##        @classmethod
        def create_from_ndarray(cls, value, extra, lBound=0):
            #c:/python25/lib/site-packages/numpy/ctypeslib.py
            numpy = __import__("numpy.ctypeslib")

            # SAFEARRAYs have Fortran order; convert the numpy array if needed
            if not value.flags.f_contiguous:
                value = numpy.array(value, order="F")

            ai = value.__array_interface__
            if ai["version"] != 3:
                raise TypeError("only __array_interface__ version 3 supported")
            if cls._itemtype_ != numpy.ctypeslib._typecodes[ai["typestr"]]:
                raise TypeError("Wrong array item type")

            # For VT_UNKNOWN or VT_DISPATCH, extra must be a pointer to
            # the GUID of the interface.
            #
            # For VT_RECORD, extra must be a pointer to an IRecordInfo
            # describing the record.
            rgsa = (_safearray.SAFEARRAYBOUND * value.ndim)()
            nitems = 1
            for i, d in enumerate(value.shape):
                nitems *= d
                rgsa[i].cElements = d
                rgsa[i].lBound = lBound
            pa = _safearray.SafeArrayCreateEx(cls._vartype_,
                                              value.ndim, # cDims
                                              rgsa, # rgsaBound
                                              extra) # pvExtra
            if not pa:
                if cls._vartype_ == VT_RECORD and extra is None:
                    raise TypeError("Cannot create SAFEARRAY type VT_RECORD without IRecordInfo.")
                # Hm, there may be other reasons why the creation fails...
                raise MemoryError()
            # We now have a POINTER(tagSAFEARRAY) instance which we must cast
            # to the correct type:
            pa = cast(pa, cls)
            # Now, fill the data in:
            ptr = POINTER(cls._itemtype_)() # pointer to the item values
            _safearray.SafeArrayAccessData(pa, byref(ptr))
            try:
                nbytes = nitems * sizeof(cls._itemtype_)
                memmove(ptr, value.ctypes.data, nbytes)
            finally:
                _safearray.SafeArrayUnaccessData(pa)
            return pa
        create_from_ndarray = classmethod(create_from_ndarray)

##        @classmethod
        def from_param(cls, value):
            if not isinstance(value, cls):
                value = cls.create(value, extra)
                value._needsfree = True
            return value
        from_param = classmethod(from_param)

        def __getitem__(self, index):
            # pparray[0] returns the whole array contents.
            if index != 0:
                raise IndexError("Only index 0 allowed")
            return self.unpack()

        def __setitem__(self, index, value):
            # XXX Need this to implement [in, out] safearrays in COM servers!
##            print "__setitem__", index, value
            raise TypeError("Setting items not allowed")

        def __ctypes_from_outparam__(self):
            self._needsfree = True
            return self[0]

        def __del__(self):
            if self._needsfree:
                _safearray.SafeArrayDestroy(self)

        def _get_size(self, dim):
            "Return the number of elements for dimension 'dim'"
            return _safearray.SafeArrayGetUBound(self, dim)+1 - _safearray.SafeArrayGetLBound(self, dim)

        def unpack(self):
            """Unpack a POINTER(SAFEARRAY_...) into a Python tuple."""
            dim = _safearray.SafeArrayGetDim(self)

            if dim == 1:
                num_elements = self._get_size(1)
                return tuple(self._get_elements_raw(num_elements))
            elif dim == 2:
                # get the number of elements in each dimension
                rows, cols = self._get_size(1), self._get_size(2)
                # get all elements
                result = self._get_elements_raw(rows * cols)
                # transpose the result, because it is in VB order
                #result = [tuple(result[r::rows]) for r in range(rows)]
                #return tuple(result)
		return result
            else:
                lowerbounds = [_safearray.SafeArrayGetLBound(self, d) for d in range(1, dim+1)]
                indexes = (c_long * dim)(*lowerbounds)
                upperbounds = [_safearray.SafeArrayGetUBound(self, d) for d in range(1, dim+1)]
                return self._get_row(0, indexes, lowerbounds, upperbounds)

        def _get_elements_raw(self, num_elements):
            """Returns a flat list containing ALL elements in the safearray."""
            from comtypes.automation import VARIANT
            # XXX Not sure this is true:
            # For VT_UNKNOWN and VT_DISPATCH, we should retrieve the
            # interface iid by SafeArrayGetIID().
            ptr = POINTER(self._itemtype_)() # container for the values
            _safearray.SafeArrayAccessData(self, byref(ptr))
            try:
                if self._itemtype_ == VARIANT:
                    return [i.value for i in ptr[:num_elements]]
                elif issubclass(self._itemtype_, POINTER(IUnknown)):
                    iid = _safearray.SafeArrayGetIID(self)
                    itf = com_interface_registry[str(iid)]
                    # COM interface pointers retrieved from array
                    # must be AddRef()'d if non-NULL.
                    elems = ptr[:num_elements]
                    result = []
                    for p in elems:
                        if bool(p):
                            p.AddRef()
                            result.append(p.QueryInterface(itf))
                        else:
                            # return a NULL-interface pointer.
                            result.append(POINTER(itf)())
                    return result
                else:
                    # If the safearray element are NOT native python
                    # objects, the containing safearray must be kept
                    # alive until all the elements are destroyed.
                    if not issubclass(self._itemtype_, Structure):
                        # Creating and returning numpy arrays instead
                        # of Python tuple from a safearray is a lot faster,
                        # but only for large arrays because of a certain overhead.
                        # Also, for backwards compatibility, some clients expect
                        # a Python tuple - so there should be a way to select
                        # what should be returned.  How could that work?
                        # A hack which would return numpy arrays
                        # instead of Python lists.  To be effective,
                        # the result must not converted into a tuple
                        # in the caller so there must be changes as
                        # well!

                        # Crude hack to create and attach an
                        # __array_interface__ property to the
                        # pointer instance
                        array_type = ptr._type_ * num_elements
                        if not hasattr(array_type, "__array_interface__"):
                            import numpy.ctypeslib
                            numpy.ctypeslib.prep_array(array_type)
                        # use the array_type's __array_interface__, ...
                        aif = array_type.__array_interface__.__get__(ptr)
                        # overwrite the 'data' member so that it points to the
                        # address we want to use
                        aif["data"] = (cast(ptr, c_void_p).value, False)
                        ptr.__array_interface__ = aif
			import numpy
                        return numpy.array(ptr, copy=True)
                        return ptr[:num_elements]
                    def keep_safearray(v):
                        v.__keepref = self
                        return v
                    return [keep_safearray(x) for x in ptr[:num_elements]]
            finally:
                _safearray.SafeArrayUnaccessData(self)

        def _get_row(self, dim, indices, lowerbounds, upperbounds):
            # loop over the index of dimension 'dim'
            # we have to restore the index of the dimension we're looping over
            restore = indices[dim]

            result = []
            obj = self._itemtype_()
            pobj = byref(obj)
            if dim+1 == len(indices):
                # It should be faster to lock the array and get a whole row at once?
                # How to calculate the pointer offset?
                for i in range(indices[dim], upperbounds[dim]+1):
                    indices[dim] = i
                    _safearray.SafeArrayGetElement(self, indices, pobj)
                    result.append(obj.value)
            else:
                for i in range(indices[dim], upperbounds[dim]+1):
                    indices[dim] = i
                    result.append(self._get_row(dim+1, indices, lowerbounds, upperbounds))
            indices[dim] = restore
            return tuple(result) # for compatibility with pywin32.

    class _(partial, POINTER(POINTER(sa_type))):

##        @classmethod
        def from_param(cls, value):
            if isinstance(value, cls._type_):
                return byref(value)
            return byref(cls._type_.create(value, extra))
        from_param = classmethod(from_param)

        def __setitem__(self, index, value):
            # create an LP_SAFEARRAY_... instance
            pa = self._type_.create(value, extra)
            # XXX Must we destroy the currently contained data?
            # fill it into self
            super(POINTER(POINTER(sa_type)), self).__setitem__(index, pa)

    return sa_type

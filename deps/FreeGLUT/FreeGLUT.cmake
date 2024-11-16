
orcaslicer_add_cmake_project(FreeGLUT
    URL https://github.com/FreeGLUTProject/freeglut/archive/refs/heads/master.zip
    CMAKE_ARGS
        -DCMAKE_INSTALL_PREFIX:STRING=${DESTDIR}
        -DBUILD_SHARED_LIBS:BOOL=OFF
        -DFREEGLUT_BUILD_DEMOS:BOOL=OFF
        -DGLUT_INCLUDE_DIR=sys/include
        -DGLUT_glut_LIBRARY=sys/lib/freeglut.lib
        -DCMAKE_C_FLAGS="/Dstrncasecmp=_strnicmp"
)
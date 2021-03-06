

import setuptools


with open('README.md', 'rb') as f:
    long_description = f.read().decode()


setuptools.setup(
    name = 'jupylet',
    packages = ['jupylet'],
    version = '0.8.0',
    license='bsd-2-clause',
    description = 'Python game programming in Jupyter notebooks.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author = 'Nir Aides',
    author_email = 'nir@winpdb.org',
    url = 'https://github.com/nir/jupylet',
    download_url = 'https://github.com/nir/jupylet/archive/v0.8.0.tar.gz',
    keywords = [
        'python', 
        'pyglet', 
        'jupyter', 
        'kids', 
        'games', 
        'children',
        'midi', 
        'synthesizers',
        'deep learning', 
        'reinforcement learning', 
        'RL',
    ],
    install_requires=[
        'wget',
        'numpy', 
        'PyGLM',
        'scipy', 
        'pillow', 
        'gltflib',
        'jupyter',
        'moderngl',
        'soundfile',
        'webcolors', 
        'ipyevents', 
        'ipywidgets', 
        'matplotlib', 
        'sounddevice', 
        'xvfbwrapper',
        'scikit-image',
        'moderngl-window',
    ],
    extras_require = {
        'midi': ['mido', 'python-rtmidi']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Education',
        'Intended Audience :: Developers', 
        'Intended Audience :: Science/Research',
        'Topic :: Education',
        'Topic :: Multimedia :: Graphics',
        'Topic :: Multimedia :: Graphics :: 3D Rendering',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: MIDI',
        'Topic :: Multimedia :: Sound/Audio :: Sound Synthesis',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)


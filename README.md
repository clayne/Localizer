[![License](http://img.shields.io/:license-MIT-blue.svg)](https://github.com/yugr/Localizer/blob/master/LICENSE.txt)

# What is this

Localizer is a simple experimental tool
which tries to detect symbols which could localized within their module
i.e. be marked as `static` or moved to anon. namespace.

Localization of symbols is beneficial because it
[enables optimizations](https://embeddedgurus.com/stack-overflow/2008/12/efficient-c-tips-5-make-local-functions-static/)
and prevents interface pollution.

The tool works by intercepting calls to linker and
analyzing symbol imports and exports.

# How to run

Run your build script under `find-locals.py` script:
```
$ find-locals.py make -j10 clean all
```

If you want to ignore symbols which are present in headers, do
```
$ find-locals.py --ignore-header-symbols $PWD make ...
```

In many cases symbols are exported so that they can be used in unit tests
so you may need to build tests as well:
```
$ find-locals.py 'make -j10 && make -j10 check'
```

For more options, run `find-locals.py -h`.

# How to test

Run
```
$ test/run_tests.sh
```

# Limitations

By design the tool is unable to detect conditional uses of symbols
which are hidden under `#ifdef`s.

Sometimes compiler is also clever enough to optimize out function calls
even if they are present in text (e.g. by propagating constant arguments
into static functions). For this reason it's recommended to run the tool
on _unoptimized_ build, to disable function inlining and cloning.
For Autotools-enabled projects just do
```
$ ./configure CFLAGS='-g -O0' CXXFLAGS='-g -O0'
```

Finally, there's no need to report unused C++ methods
as there's no way to localize them. But I still do this
because they can't be distinguished from symbols in namespaces
which _can_ be localized (by moving them to anon. namespaces).

# Findings

* 15 symbols in [GNU awk](https://lists.gnu.org/archive/html/bug-gawk/2021-03/msg00001.html)
* 4 symbols in GNU bc (private communication)
* 18 symbols in [GNU screen](https://lists.gnu.org/archive/html/screen-devel/2021-03/msg00000.html)
* 6 symbols in [GNU make](https://lists.gnu.org/archive/html/bug-make/2021-03/msg00021.html)
* 100+ symbols in [QEMU](https://mail.gnu.org/archive/html/qemu-devel/2021-03/msg07706.html)

# TODO

* Integrate LGTM, Codecov and Travis
* Do not report virtual methods (they aren't directly used in other files)
* Report C++ symbols only if they are in namespaces (not classes)

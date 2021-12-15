zipstream-ng changelog
======================

### [v1.3.3]
- Fix issue where directly adding an empty folder would give it the wrong name in the archive and
  lead to an incorrect zip size being calculated.

### [v1.3.2]
- Fix documentation issue caused by the import shuffling in v1.3.1
- Set external attributes (permissions, directory flag, etc) on data added to the `ZipStream` via `add()`

### [v1.3.1]
- Allow importing functionality from `zipstream.ng` as well as `zipstream` to avoid namespace
  collisions with other projects that provide a `zipstream` module.

### [v1.3.0]
- Add a `last_modified` property to `ZipStream` objects that returns a `datetime` of the most recent
  modified date of all the files in the stream.

### [v1.2.1]
- Fix issue where adding empty directories would lead to an incorrect zip size being calculated.
- Fix issue where asking for the `ZipStream`'s size multiple times while adding data wouldn't
  properly check if Zip64 extensions were being used, causing an incorrect size to be calculated.

### [v1.2.0]
- Add a `sized` property to `ZipStream` objects that checks if the size can be calculated for it
- Change `ZipStream.from_path` to generate a sized `ZipStream` if no compression is used

### [v1.1.0]
- Add support for Python 3.5 and 3.6

### [v1.0.0]
- Initial version

 [v1.0.0]: https://github.com/pR0Ps/zipstream-ng/commit/72b2721c0593fb99fdc2d9537f52b1c3bc1d736f
 [v1.1.0]: https://github.com/pR0Ps/zipstream-ng/compare/v1.0.0...v1.1.0
 [v1.2.0]: https://github.com/pR0Ps/zipstream-ng/compare/v1.1.0...v1.2.0
 [v1.2.1]: https://github.com/pR0Ps/zipstream-ng/compare/v1.2.0...v1.2.1
 [v1.3.0]: https://github.com/pR0Ps/zipstream-ng/compare/v1.2.1...v1.3.0
 [v1.3.1]: https://github.com/pR0Ps/zipstream-ng/compare/v1.3.0...v1.3.1
 [v1.3.2]: https://github.com/pR0Ps/zipstream-ng/compare/v1.3.1...v1.3.2
 [v1.3.3]: https://github.com/pR0Ps/zipstream-ng/compare/v1.3.2...v1.3.3

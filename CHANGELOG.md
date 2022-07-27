# Changelog All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [2022.7.0]

Initial release of bluesky-cmds, the origins of this application lie with [yaqc-cmds](https://github.com/wright-group/yaqc-cmds).

### Removed
- yaqc dependency
- custom built orchestration layer
- direct hardware interfacing
- unused code

### Changed
- Completely rearchitect to use [bluesky-queueserver](https://github.com/bluesky/bluesky-queueserver)

### Added
- support for pyqt5 (via qtpy)


[Unreleased]: https://github.com/wright-group/bluesky-cmds/compare/v2022.7.0...master
[2022.7.0]: https://github.com/wright-group/bluesky-cmds/releases/tag/v2020.7.0

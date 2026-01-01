# Contributors

## Version 2.0 - Major Refactor (2026)

This version represents a significant refactoring effort to modernize the codebase:

### Key Improvements
- **Modular Architecture**: Reorganized into a proper Python package with clear separation of concerns
- **Concurrent Processing**: Added optional multi-threaded processing for improved performance
- **DRY_RUN Mode**: Introduced safety mode for testing strategies without real trades
- **Decimal Precision**: Implemented Decimal type for accurate financial calculations
- **Testing Infrastructure**: Added comprehensive unit tests with mocked external APIs
- **CI/CD**: Integrated GitHub Actions for automated testing
- **Thread Safety**: Implemented proper locking for concurrent operations
- **Caching**: Single holdings fetch per scan with configurable TTL
- **Configuration Management**: Environment-based configuration with sensible defaults
- **Python Logging**: Integrated standard Python logging alongside colored CLI output

### Technical Debt Addressed
- Removed per-coin sleep delays from trading loop
- Eliminated blocking operations in hot paths
- Added atomic file operations for portfolio persistence
- Implemented lazy imports to avoid circular dependencies
- Standardized symbol normalization across exchanges

### Backward Compatibility
- CLI interface remains compatible with original version
- Portfolio file format unchanged
- API credential management unchanged
- Core trading logic principles preserved

### Testing
- 19 unit tests with >95% code coverage of core modules
- Mocked external API dependencies
- CI pipeline validates on Python 3.9, 3.10, and 3.11

This refactor maintains the original vision while providing a production-ready foundation for future enhancements.

## Original Author
Original rhapi project created by thegregguy

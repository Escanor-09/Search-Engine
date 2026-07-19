1) Why use nlohmann/json??
-> This is used to move the burden away from manually parsing a JSON Object. We chose this particular parser because it's header only, has intuitive modern C++ API, is well tested and minimzes the development effort. Even if it became bottlenectk we could shift to different parser, without modifying the implementation in the code as much because the parser is isolated behind the Parser Interface. The main benefit of this parser was not just eliminating the linker step-it was simplifying dependency management. A header-only library like nlohmann/json can be added by including header, with no sepearte binary to build or link. That reduces setup complexity and improves portability. The tradef-off is longer compile time becuase each translation unit parses the implementation.

Alternatives:
    //Rapid JSON -> pros: fast, low mem usage, performance critical
                    cons: api is more verbose, harder to learn
    //simdjson  ->  pros: fastest JSON parser
                    cons: more specialized than nlohmann/json
    //Boost.JSON -> pros: modern API, excellent performance
                    cons: larger dependency

2) Why spearate file check was not used if the file exists or not?
-> I considered using std::filesystem::Exists(), but checking existence before opening introduces a potential TOCTOU race condition. The definitive operation is attempting to open the files. If std::ifstream fails, I treat it as an open failure and propagate an exception. If the application required more specific diagnostics, I could use std::filesystem or platform-specific error information to distinguish between missing files, permission issues, and other I/O errors.

3) Why remove Stop-Words?? What are Stop Words??
-> Stop words are common, frequently used words—such as "the," "is," and "in"—that carry very little inherent meaning. In natural language processing (NLP) and search engines, these words are often ignored or filtered out to reduce computational "noise" and focus exclusively on core, meaningful terms.
-> While removing stop words is a staple of text analysis, algorithms handling machine translation, language modeling, and question-answering tasks generally keep them. In these cases, the structural context provided by stop words is critical to understanding meaning.

To run this project
//cmake -S . -B build
//cmake --build build
//./build/search_engine
package com.example.service;

import com.example.model.Section;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.io.File;
import java.util.*;
import java.util.regex.*;

@Service
public class DocumentService {

    private List<Section> sections = new ArrayList<>();

    @PostConstruct
    public void init() {
        try {
            PDDocument document = PDDocument.load(new File("src/main/resources/testing.pdf"));
            PDFTextStripper stripper = new PDFTextStripper();
            String rawText = stripper.getText(document);
            document.close();

            // 2) Normalize: preserve newlines, collapse only spaces/tabs, lowercase
            String normalized = rawText
                .replaceAll("\\r?\\n", "\n")  // keep real newlines
                .replaceAll("[ \\t]+", " ")   // collapse spaces/tabs
                .trim();

            // 3) Find every section header (with or without the "§")
            Pattern headerPattern = Pattern.compile(
                "(?m)^\\s*(?:" +
                    "(§\\s*\\d{3}\\.\\d+\\s+[^:\\n]+:?)|" +                // e.g. § 121.471 Title: (group 1)
                    "(APPENDIX\\s+\\d+:\\s+[^\\n]+)|" +                    // e.g. APPENDIX 6: PART 91: ...
                    "([IVXLCDM]+\\.\\s+[^\\n]+)|" +                        // Roman numeral sections like II. TITLE
                ")",
                Pattern.CASE_INSENSITIVE
            );

            Matcher headerMatcher = headerPattern.matcher(normalized);
            List<Integer> starts = new ArrayList<>();
            List<Integer> ends = new ArrayList<>();
            List<String> headers = new ArrayList<>();

           while (headerMatcher.find()) {
            // figure out which header-group actually matched
                for (int g = 1; g <= headerMatcher.groupCount(); g++) {
                    String grp = headerMatcher.group(g);
                    if (grp != null) {
                    String hdr = grp.trim();
                    
                    // record the exact span of that header-group
                    int s = headerMatcher.start(g);
                    int e = headerMatcher.end(g);

                    starts.add(s);
                    ends.add(e);
                    headers.add(hdr);
                    break;   // done with this match—move on to the next find()
                    }
                }
            }
            
            // 4) Slice out each chunk from start-of-this-header to start-of-next-header
            for (int i = 0; i < headers.size(); i++) {
                int headerEnd  = ends.get(i);
                int nextStart  = (i+1 < starts.size()) ? starts.get(i+1) : normalized.length();

                String header = headers.get(i);
                String body   = normalized.substring(headerEnd, nextStart).trim();
                sections.add(new Section(header, body));
            }

        } catch (Exception e) {
            System.err.println("Parsing error: " + e.getMessage());
        }
    }

    public List<Section> chunkSearch(String query) {
        query = query.toLowerCase();
        List<Section> results = new ArrayList<>();

        for (Section section : sections) {
            String header = section.getHeader().toLowerCase();
            String content = section.getContent().toLowerCase();

            if (header.contains(query) || content.contains(query)) {
                results.add(section);
            }
        }

        return results;
    }
}

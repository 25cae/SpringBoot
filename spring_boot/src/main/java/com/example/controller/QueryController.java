package com.example.controller;

import com.example.model.Section;
import com.example.service.DocumentService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
public class QueryController {

    private final DocumentService documentService;

    public QueryController(DocumentService documentService) {
        this.documentService = documentService;
    }

    @GetMapping("/search")
    public List<Section> search(@RequestParam String q,
                                @RequestParam(defaultValue = "3") int limit) {
        return documentService.chunkSearch(q);
    }
}

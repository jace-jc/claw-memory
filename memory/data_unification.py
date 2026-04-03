"""
Data Unification - Consolidates memory from multiple sources

Problem: Three systems each storing 181 duplicate memories = 543 total (67% waste)
- OpenClaw memory/*.md: 181 memories
- SuperMemory (localhost:3001): 181 memories
- Mem0 (localhost:3002): 181 memories

Solution: Deduplicate by content hash, create unified single source of truth.
"""
import os
import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Set, Optional
from pathlib import Path
import re

_logger = logging.getLogger(__name__)


class MemoryUnifier:
    """
    Unifies memories from multiple sources by content hash deduplication.
    
    Sources:
    1. OpenClaw workspace memory/*.md files
    2. SuperMemory API (localhost:3001)
    3. Mem0 API (localhost:3002)
    """
    
    def __init__(self, 
                 memory_path: str = "/Users/claw/.openclaw/workspace/memory",
                 output_path: str = "/Users/claw/.openclaw/workspace/memory/unification_report.json"):
        self.memory_path = Path(memory_path)
        self.output_path = Path(output_path)
        self.deduplicated_path = Path("/Users/claw/.openclaw/workspace/memory/deduplicated_memories.json")
        
        # Ensure directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute SHA256 hash of content"""
        # Normalize: strip whitespace, lowercase for comparison
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    
    def scan_openclaw_memories(self) -> List[Dict]:
        """
        Scan OpenClaw memory/*.md files for memories.
        
        Returns:
            List of memory dicts with content, source, id
        """
        memories = []
        
        if not self.memory_path.exists():
            _logger.warning(f"Memory path not found: {self.memory_path}")
            return memories
        
        # Scan all md files in memory directory
        for md_file in self.memory_path.glob("*.md"):
            if md_file.name in ["MEMORY.md", "README.md", "CHANGELOG.md"]:
                continue
            
            try:
                content = md_file.read_text(encoding="utf-8")
                
                # Extract individual memories (separated by ## or ### headers)
                sections = re.split(r'^#{1,3}\s+', content, flags=re.MULTILINE)
                
                for section in sections:
                    section = section.strip()
                    if len(section) < 10:  # Skip very short sections
                        continue
                    
                    # Use first line as title, rest as content
                    lines = section.split("\n")
                    title = lines[0][:100] if lines else ""
                    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
                    
                    if len(body) < 10:
                        body = section  # Use whole section if no clear title
                    
                    memories.append({
                        "content": body[:500] if len(body) > 500 else body,  # Truncate long content
                        "title": title,
                        "source": "openclaw",
                        "source_file": str(md_file.name),
                        "content_hash": self.compute_content_hash(body)
                    })
                    
            except Exception as e:
                _logger.warning(f"Failed to read {md_file}: {e}")
        
        _logger.info(f"Scanned OpenClaw memories: {len(memories)} found")
        return memories
    
    def query_supermemory_api(self) -> List[Dict]:
        """Query SuperMemory API if available"""
        memories = []
        
        try:
            import requests
            response = requests.get(
                "http://localhost:3001/api/memories",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                memories_raw = data.get("memories", data.get("data", []))
                
                for mem in memories_raw:
                    content = mem.get("content", mem.get("text", ""))
                    if content:
                        memories.append({
                            "content": content[:500] if len(content) > 500 else content,
                            "source": "supermemory",
                            "memory_id": mem.get("id", ""),
                            "content_hash": self.compute_content_hash(content)
                        })
                
                _logger.info(f"SuperMemory API: {len(memories)} memories")
            else:
                _logger.debug(f"SuperMemory API returned status {response.status_code}")
                
        except ImportError:
            _logger.debug("requests not available for SuperMemory API")
        except Exception as e:
            _logger.debug(f"SuperMemory API unavailable: {e}")
        
        return memories
    
    def query_mem0_api(self) -> List[Dict]:
        """Query Mem0 API if available"""
        memories = []
        
        try:
            import requests
            response = requests.get(
                "http://localhost:3002/api/memories",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                memories_raw = data.get("memories", data.get("data", []))
                
                for mem in memories_raw:
                    content = mem.get("content", mem.get("text", ""))
                    if content:
                        memories.append({
                            "content": content[:500] if len(content) > 500 else content,
                            "source": "mem0",
                            "memory_id": mem.get("id", ""),
                            "content_hash": self.compute_content_hash(content)
                        })
                
                _logger.info(f"Mem0 API: {len(memories)} memories")
            else:
                _logger.debug(f"Mem0 API returned status {response.status_code}")
                
        except ImportError:
            _logger.debug("requests not available for Mem0 API")
        except Exception as e:
            _logger.debug(f"Mem0 API unavailable: {e}")
        
        return memories
    
    def deduplicate(self, all_memories: List[Dict]) -> List[Dict]:
        """
        Deduplicate memories by content hash.
        
        Keeps first occurrence of each unique content.
        Records all sources for each unique memory.
        """
        seen_hashes = {}
        unique_memories = []
        
        for mem in all_memories:
            content_hash = mem.get("content_hash")
            if not content_hash:
                content_hash = self.compute_content_hash(mem.get("content", ""))
            
            if content_hash not in seen_hashes:
                seen_hashes[content_hash] = True
                mem["unique_id"] = content_hash
                mem["first_seen_at"] = datetime.now().isoformat()
                mem["sources"] = [mem.get("source", "unknown")]
                unique_memories.append(mem)
            else:
                # Mark duplicate source
                for unique_mem in unique_memories:
                    if unique_mem.get("unique_id") == content_hash:
                        if mem.get("source") not in unique_mem.get("sources", []):
                            unique_mem["sources"].append(mem.get("source", "unknown"))
                        break
        
        return unique_memories
    
    def unify(self) -> Dict:
        """
        Main entry point: unify all memory sources.
        
        Returns:
            Report dict with unification statistics
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "sources": {}
        }
        
        # Step 1: Collect from all sources
        all_memories = []
        
        # OpenClaw memories
        openclaw_memories = self.scan_openclaw_memories()
        all_memories.extend(openclaw_memories)
        report["sources"]["openclaw"] = {
            "count": len(openclaw_memories),
            "path": str(self.memory_path)
        }
        
        # SuperMemory API
        supermemory_memories = self.query_supermemory_api()
        if supermemory_memories:
            all_memories.extend(supermemory_memories)
            report["sources"]["supermemory"] = {
                "count": len(supermemory_memories),
                "endpoint": "http://localhost:3001/api/memories"
            }
        
        # Mem0 API
        mem0_memories = self.query_mem0_api()
        if mem0_memories:
            all_memories.extend(mem0_memories)
            report["sources"]["mem0"] = {
                "count": len(mem0_memories),
                "endpoint": "http://localhost:3002/api/memories"
            }
        
        report["total_found"] = len(all_memories)
        
        # Step 2: Deduplicate
        unique_memories = self.deduplicate(all_memories)
        
        report["unique_memories"] = len(unique_memories)
        report["duplicates_eliminated"] = len(all_memories) - len(unique_memories)
        report["deduplication_rate"] = f"{(1 - len(unique_memories)/len(all_memories))*100:.1f}%" if all_memories else "0%"
        
        # Source breakdown for unique memories
        source_breakdown = {}
        for mem in unique_memories:
            for source in mem.get("sources", []):
                source_breakdown[source] = source_breakdown.get(source, 0) + 1
        report["unique_by_source"] = source_breakdown
        
        # Step 3: Save deduplicated memories
        self.deduplicated_path.parent.mkdir(parents=True, exist_ok=True)
        self.deduplicated_path.write_text(
            json.dumps({
                "memories": unique_memories,
                "count": len(unique_memories),
                "generated_at": datetime.now().isoformat()
            }, indent=2, ensure_ascii=False)
        )
        report["deduplicated_file"] = str(self.deduplicated_path)
        
        # Step 4: Save report
        self.output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        report["report_file"] = str(self.output_path)
        
        _logger.info(f"Unification complete: {report}")
        return report


def get_memory_stats() -> Dict:
    """Quick stats about memory unification"""
    unifier = MemoryUnifier()
    return unifier.unify()

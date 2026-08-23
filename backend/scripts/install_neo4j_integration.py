#!/usr/bin/env python
"""
Installation script for Neo4j integration with the Knowledge Graph.
This script installs the required dependencies and sets up the environment.
"""

import os
import sys
import subprocess
import argparse
import logging
import shutil
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = [
    "neo4j>=5.0.0",
    "networkx>=2.5",
    "matplotlib>=3.4.0",
    "spacy>=3.0.0",
]

# Environment variables to set
DEFAULT_ENV_VARS = {
    "NEO4J_ENABLED": "false",
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "password",
    "NEO4J_DATABASE": "neo4j",
}

def check_dependencies():
    """Check if required dependencies are installed."""
    missing_packages = []
    
    for package in REQUIRED_PACKAGES:
        package_name = package.split('>=')[0]
        try:
            __import__(package_name)
            logger.info(f"✓ {package_name} is installed")
        except ImportError:
            missing_packages.append(package)
            logger.warning(f"✗ {package_name} is missing")
    
    return missing_packages

def install_dependencies(missing_packages):
    """Install missing dependencies."""
    if not missing_packages:
        logger.info("All dependencies are already installed.")
        return True
    
    logger.info("Installing missing dependencies...")
    
    for package in missing_packages:
        logger.info(f"Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            logger.info(f"✓ Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed to install {package}: {e}")
            return False
    
    return True

def download_spacy_model(model_name="en_core_web_sm"):
    """Download spaCy language model if not already installed."""
    try:
        import spacy
        try:
            spacy.load(model_name)
            logger.info(f"✓ spaCy model {model_name} is already installed")
            return True
        except OSError:
            logger.info(f"Downloading spaCy model {model_name}...")
            subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])
            logger.info(f"✓ Successfully downloaded spaCy model {model_name}")
            return True
    except ImportError:
        logger.error("✗ spaCy is not installed. Please install it first.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Failed to download spaCy model: {e}")
        return False

def set_environment_variables(env_vars=None):
    """Set environment variables for Neo4j connection."""
    if env_vars is None:
        env_vars = DEFAULT_ENV_VARS
    
    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"Set environment variable {key}={value}")
    
    return True

def create_env_file(env_vars=None, filename=".env"):
    """Create .env file with Neo4j connection details."""
    if env_vars is None:
        env_vars = DEFAULT_ENV_VARS
    
    with open(filename, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    logger.info(f"Created .env file: {filename}")
    return True

def check_neo4j_connection(uri, username, password, database):
    """Test connection to Neo4j database."""
    try:
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        with driver.session(database=database) as session:
            result = session.run("RETURN 1 AS test")
            record = result.single()
            if record and record["test"] == 1:
                logger.info("✓ Successfully connected to Neo4j")
                driver.close()
                return True
            else:
                logger.error("✗ Failed to validate Neo4j connection")
                driver.close()
                return False
                
    except ImportError:
        logger.error("✗ Neo4j driver is not installed")
        return False
    except Exception as e:
        logger.error(f"✗ Failed to connect to Neo4j: {e}")
        return False

def setup_neo4j_database(uri, username, password, database):
    """Set up Neo4j database with necessary indexes and constraints."""
    try:
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        with driver.session(database=database) as session:
            # Create constraints
            try:
                # Check if APOC is available
                apoc_result = session.run("CALL dbms.procedures() YIELD name WHERE name STARTS WITH 'apoc' RETURN count(*) as count")
                apoc_available = apoc_result.single()["count"] > 0
                
                if apoc_available:
                    logger.info("✓ APOC extensions are available in Neo4j")
                else:
                    logger.warning("⚠ APOC extensions are not available in Neo4j. Some functionality may be limited.")
                
                # Create entity ID constraint
                try:
                    # Neo4j 4.x+ syntax
                    session.run("""
                    CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                    FOR (e:Entity)
                    REQUIRE e.id IS UNIQUE
                    """)
                except Exception:
                    # Older Neo4j syntax
                    try:
                        session.run("""
                        CREATE CONSTRAINT ON (e:Entity)
                        ASSERT e.id IS UNIQUE
                        """)
                    except Exception as e:
                        logger.warning(f"⚠ Could not create constraint for Entity ID: {e}")
                
                logger.info("✓ Successfully created database constraints")
                
            except Exception as e:
                logger.warning(f"⚠ Error setting up constraints: {e}")
            
            driver.close()
            return True
            
    except Exception as e:
        logger.error(f"✗ Failed to set up Neo4j database: {e}")
        return False

def configure_knowledge_graph_module(project_dir="."):
    """Configure the knowledge_graph module in the project."""
    # Create knowledge_graph directory if it doesn't exist
    kg_dir = os.path.join(project_dir, "knowledge_graph")
    os.makedirs(kg_dir, exist_ok=True)
    
    # Ensure __init__.py exists
    init_file = os.path.join(kg_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("""\"\"\"
Knowledge graph module for enhanced document retrieval and querying.
\"\"\"

from .model import KnowledgeGraph, Entity, Relation
try:
    from .neo4j_integration import Neo4jIntegration
    has_neo4j = True
except ImportError:
    has_neo4j = False

__all__ = [
    'KnowledgeGraph',
    'Entity',
    'Relation',
]

if has_neo4j:
    __all__.append('Neo4jIntegration')
""")
    
    logger.info("✓ Knowledge graph module configured")
    return True

def update_requirements_file(project_dir="."):
    """Update requirements.txt with Neo4j dependencies."""
    requirements_file = os.path.join(project_dir, "requirements.txt")
    
    if not os.path.exists(requirements_file):
        logger.warning(f"⚠ requirements.txt not found at {requirements_file}")
        return False
    
    # Read existing requirements
    with open(requirements_file, "r") as f:
        requirements = f.read()
    
    # Add required packages if not already present
    modified = False
    for package in REQUIRED_PACKAGES:
        package_name = package.split('>=')[0]
        if package_name not in requirements:
            requirements += f"\n{package}"
            modified = True
    
    # Write updated requirements
    if modified:
        with open(requirements_file, "w") as f:
            f.write(requirements)
        logger.info("✓ Updated requirements.txt with Neo4j dependencies")
    else:
        logger.info("✓ requirements.txt already contains required dependencies")
    
    return True

def main():
    """Main installation function."""
    parser = argparse.ArgumentParser(description="Install Neo4j integration for Knowledge Graph")
    parser.add_argument("--uri", default=DEFAULT_ENV_VARS["NEO4J_URI"], help="Neo4j URI")
    parser.add_argument("--username", default=DEFAULT_ENV_VARS["NEO4J_USERNAME"], help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_ENV_VARS["NEO4J_PASSWORD"], help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_ENV_VARS["NEO4J_DATABASE"], help="Neo4j database name")
    parser.add_argument("--enable", action="store_true", help="Enable Neo4j integration")
    parser.add_argument("--project-dir", default=".", help="Project directory")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--test-connection", action="store_true", help="Test Neo4j connection")
    parser.add_argument("--setup-database", action="store_true", help="Set up Neo4j database")
    parser.add_argument("--spacy-model", default="en_core_web_sm", help="spaCy model to download")
    
    args = parser.parse_args()
    
    # Create environment variables dict
    env_vars = {
        "NEO4J_ENABLED": "true" if args.enable else "false",
        "NEO4J_URI": args.uri,
        "NEO4J_USERNAME": args.username,
        "NEO4J_PASSWORD": args.password,
        "NEO4J_DATABASE": args.database,
    }
    
    logger.info("Starting Neo4j integration installation...")
    
    # Check and install dependencies
    missing_packages = check_dependencies()
    if not install_dependencies(missing_packages):
        logger.error("Failed to install dependencies")
        return 1
    
    # Download spaCy model
    if not download_spacy_model(args.spacy_model):
        logger.error("Failed to download spaCy model")
        return 1
    
    # Set environment variables
    if not set_environment_variables(env_vars):
        logger.error("Failed to set environment variables")
        return 1
    
    # Create .env file
    if not create_env_file(env_vars, args.env_file):
        logger.error("Failed to create .env file")
        return 1
    
    # Configure knowledge graph module
    if not configure_knowledge_graph_module(args.project_dir):
        logger.error("Failed to configure knowledge graph module")
        return 1
    
    # Update requirements.txt
    update_requirements_file(args.project_dir)
    
    # Test Neo4j connection if requested
    if args.test_connection or args.setup_database:
        logger.info(f"Testing connection to Neo4j at {args.uri}...")
        if not check_neo4j_connection(args.uri, args.username, args.password, args.database):
            logger.error("Failed to connect to Neo4j")
            return 1
        
        # Set up Neo4j database if requested
        if args.setup_database:
            logger.info(f"Setting up Neo4j database {args.database}...")
            if not setup_neo4j_database(args.uri, args.username, args.password, args.database):
                logger.error("Failed to set up Neo4j database")
                return 1
    
    logger.info("✓ Neo4j integration successfully installed!")
    
    # Instructions for next steps
    logger.info("\nNext steps:")
    logger.info("1. Make sure Neo4j is running")
    logger.info("2. Launch your Streamlit app: streamlit run streamlit-app.py")
    logger.info("3. Go to the Knowledge Graph tab to explore your data")
    logger.info("4. Enable Neo4j integration in the Knowledge Graph settings")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace ClassMapper
{
    class Program
    {
        static int Main(string[] args)
        {
            if (args.Length != 1)
            {
                Console.WriteLine("Usage: dotnet run -- <directory_path>");
                return 1;
            }

            string directoryPath = args[0];

            if (!Directory.Exists(directoryPath))
            {
                Console.WriteLine($"Directory not found: {directoryPath}");
                return 1;
            }

            // Find all .cs files in the directory
            string[] csFiles = Directory.GetFiles(directoryPath, "*.cs", SearchOption.AllDirectories);

            if (csFiles.Length == 0)
            {
                Console.WriteLine($"No .cs files found in {directoryPath}");
                return 1;
            }

            Console.WriteLine($"Found {csFiles.Length} .cs files to process");

            // Dictionary to hold the mapping of full class names to file paths
            var classToFileMapping = new Dictionary<string, string>();

            foreach (string filePath in csFiles)
            {
                Console.WriteLine($"Processing: {filePath}");
                // Process each file and add mappings to the dictionary
                ProcessCsFile(filePath, classToFileMapping);
            }

            // Output the mapping as JSON
            string outputPath = Path.Combine(directoryPath, "class_mapping.json");
            string jsonOutput = JsonSerializer.Serialize(classToFileMapping, new JsonSerializerOptions 
            { 
                WriteIndented = true 
            });
            
            File.WriteAllText(outputPath, jsonOutput);
            Console.WriteLine($"Class mapping written to: {outputPath}");

            return 0;
        }

        // Process a C# file and extract class names with their namespaces
        static void ProcessCsFile(string filePath, Dictionary<string, string> mapping)
        {
            try
            {
                string code = File.ReadAllText(filePath);
                SyntaxTree tree = CSharpSyntaxTree.ParseText(code);
                CompilationUnitSyntax root = tree.GetCompilationUnitRoot();

                // Get the namespace declarations
                var namespaceDeclarations = root.DescendantNodes().OfType<NamespaceDeclarationSyntax>();
                
                foreach (var namespaceDeclaration in namespaceDeclarations)
                {
                    string namespaceName = namespaceDeclaration.Name.ToString();
                    
                    // Get all classes in this namespace
                    var classDeclarations = namespaceDeclaration.DescendantNodes().OfType<ClassDeclarationSyntax>();
                    
                    foreach (var classDeclaration in classDeclarations)
                    {
                        string className = classDeclaration.Identifier.Text;
                        string fullClassName = $"{namespaceName}.{className}";
                        
                        // Add to mapping with normalized file path
                        mapping[fullClassName] = Path.GetFullPath(filePath);
                    }
                }
                
                // Also handle top-level classes (outside of any namespace)
                var topLevelClasses = root.DescendantNodes()
                    .OfType<ClassDeclarationSyntax>()
                    .Where(c => c.Parent is CompilationUnitSyntax);
                
                foreach (var classDeclaration in topLevelClasses)
                {
                    string className = classDeclaration.Identifier.Text;
                    // Top-level classes have no namespace
                    mapping[className] = Path.GetFullPath(filePath);
                }
                
                // Handle file-scoped namespace declarations (C# 10+)
                var fileScopedNamespace = root.DescendantNodes().OfType<FileScopedNamespaceDeclarationSyntax>().FirstOrDefault();
                if (fileScopedNamespace != null)
                {
                    string namespaceName = fileScopedNamespace.Name.ToString();
                    
                    // Get all classes in this namespace
                    var classDeclarations = fileScopedNamespace.DescendantNodes().OfType<ClassDeclarationSyntax>();
                    
                    foreach (var classDeclaration in classDeclarations)
                    {
                        string className = classDeclaration.Identifier.Text;
                        string fullClassName = $"{namespaceName}.{className}";
                        
                        // Add to mapping with normalized file path
                        mapping[fullClassName] = Path.GetFullPath(filePath);
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error processing file {filePath}: {ex.Message}");
            }
        }
    }
} 
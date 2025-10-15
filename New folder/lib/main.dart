import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

void main() {
  runApp(ClientIntelligenceApp());
}

class ClientIntelligenceApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Client Intelligence Assistant',
      theme: ThemeData(primarySwatch: Colors.indigo),
      home: CompanyInfoPage(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class CompanyInfoPage extends StatefulWidget {
  @override
  State<CompanyInfoPage> createState() => _CompanyInfoPageState();
}

class _CompanyInfoPageState extends State<CompanyInfoPage> {
  final TextEditingController _controller = TextEditingController();

  List<dynamic> searchResults = [];
  Map<String, dynamic>? companyInfo;
  bool isLoading = false;

  Future<void> searchCompany() async {
    final query = _controller.text.trim();
    if (query.isEmpty) return;

    setState(() {
      isLoading = true;
      searchResults = [];
      companyInfo = null;
    });

    try {
      final url = Uri.parse(
          'http://127.0.0.1:8000/search_companies?query=${Uri.encodeComponent(query)}');
      final res = await http.get(url);
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() => searchResults = (data['candidates'] ?? []) as List);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Search failed: ${res.statusCode}')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Search error: $e')),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> fetchCompanyInfo(String selectedName) async {
    setState(() {
      isLoading = true;
      companyInfo = null;
    });

    try {
      final url = Uri.parse(
        'http://127.0.0.1:8000/company_info?selected_name=${Uri.encodeComponent(selectedName)}',
      );
      final res = await http.get(url);
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        if (data is Map && data.containsKey('error')) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(data['error']?.toString() ?? 'Unknown error')),
          );
        } else {
          setState(() => companyInfo = data as Map<String, dynamic>);
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Fetch failed: ${res.statusCode}')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Fetch error: $e')),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  Widget _newsList(List<dynamic> news) {
    if (news.isEmpty) {
      return const Text('No recent news found.');
    }
    return Column(
      children: news.map((n) {
        final item = (n as Map<String, dynamic>);
        final title = (item['title'] ?? '').toString();
        final desc = (item['description'] ?? '').toString();
        final source = (item['source'] ?? '').toString();
        final published = (item['publishedAt'] ?? '').toString();

        return Card(
          margin: const EdgeInsets.symmetric(vertical: 6),
          elevation: 1.5,
          child: ListTile(
            title: Text(title, maxLines: 2, overflow: TextOverflow.ellipsis),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (desc.isNotEmpty)
                  Text(desc, maxLines: 2, overflow: TextOverflow.ellipsis),
                if (source.isNotEmpty || published.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4.0),
                    child: Text(
                      [source, published].where((s) => s.isNotEmpty).join(" • "),
                      style: const TextStyle(fontSize: 12, color: Colors.black54),
                    ),
                  ),
              ],
            ),
            onTap: () {
              final url = (item['url'] ?? '').toString();
              if (url.isNotEmpty) {
                // add url_launcher later if you want to open links
              }
            },
          ),
        );
      }).toList(),
    );
  }

  @override
  Widget build(BuildContext context) {
    // identical header + controls as before
    return Scaffold(
      appBar: AppBar(
        title: const Text('Client Intelligence Assistant'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _controller,
              decoration: const InputDecoration(
                labelText: 'Enter Company Name',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            ElevatedButton(onPressed: searchCompany, child: const Text('Search')),
            const SizedBox(height: 12),

            if (isLoading) const Center(child: CircularProgressIndicator()),

            // search results (same look, now as a Column so page can scroll)
            if (!isLoading && searchResults.isNotEmpty)
              ...searchResults.map((item) {
                final m = item as Map<String, dynamic>;
                final title = (m['title'] ?? '').toString();
                final snippet = (m['snippet'] ?? '').toString();
                final url = (m['url'] ?? '').toString();
                return Card(
                  child: ListTile(
                    title: Text(title),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (snippet.isNotEmpty)
                          Text(snippet, maxLines: 2, overflow: TextOverflow.ellipsis),
                        if (url.isNotEmpty)
                          Text(url, style: const TextStyle(fontSize: 12, color: Colors.blue)),
                      ],
                    ),
                    onTap: () => fetchCompanyInfo(title),
                  ),
                );
              }),

            // company section (same look, now scrolls with page)
            if (!isLoading && companyInfo != null) ...[
              const Divider(thickness: 1.5),
              Text(
                (companyInfo!['company'] ?? '').toString(),
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 6),
              Text(
                (companyInfo!['website'] ?? '').toString(),
                style: const TextStyle(color: Colors.blue),
              ),
              const SizedBox(height: 12),
              Text(
                (companyInfo!['summary'] ?? 'No summary available.').toString(),
                style: const TextStyle(fontSize: 16, height: 1.35),
              ),
              const SizedBox(height: 16),
              const Text('Latest News',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              _newsList((companyInfo!['news'] ?? []) as List),
              const SizedBox(height: 16),
            ],
          ],
        ),
      ),
    );
  }
}
